import html as _html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from supplier_common import ROOT, parse_products_from_index, parse_site_taxonomy, today_slug


COLORS = (
    "azul marinho",
    "azul escuro",
    "azul claro",
    "azul",
    "off white",
    "branco",
    "preto",
    "bege",
    "cinza claro",
    "cinza escuro",
    "cinza",
    "marrom",
    "caqui",
    "verde",
    "vermelho",
    "vinho",
    "gelo",
    "cafe",
    "café",
    "caramelo",
    "areia",
)

NOISE = {
    "xe",
    "rl",
    "hb",
    "lct",
    "arm",
    "ck",
    "preto",
    "branco",
    "bege",
    "cinza",
    "claro",
    "escuro",
    "azul",
    "marinho",
    "off",
    "white",
    "marrom",
    "caqui",
    "verde",
    "vinho",
    "gelo",
    "cafe",
    "café",
}

MATERIAL_TERMS = (
    "supima",
    "algodao egipcio",
    "algodão egípcio",
    "pima jersey",
    "pima",
    "premium",
    "linho",
    "sarja",
    "jeans",
    "moletom",
    "suede",
    "cotele",
    "cotelê",
    "corta vento",
    "corta-vento",
    "puffer",
    "bomber",
    "la batida",
    "texturizada",
)

# Sinais que mudam a identidade visual de uma peça. Eles não podem ser
# tratados como cor/tamanho; uma divergência aqui separa a peça do grupo.
STYLE_SIGNALS = {
    # Ausência de palavra não é prova de peça lisa: logo, bordado ou estampa
    # podem aparecer somente na imagem do fornecedor.
    "estampa": ("liso", "lisa", "estamp", "listr", "xadrez", "poa", "floral", "camufl", "print", "graphic", "bordad", "patch", "logo grande", "logo full"),
    "gola": ("gola polo", "gola v", "gola redonda", "meio ziper", "meio zipper", "gola alta", "capuz"),
    "fechamento": ("meio ziper", "meio zipper", "ziper", "zipped", "botoes", "botao"),
    "manga": ("manga longa", "manga curta", "regata"),
    "modelagem": ("slim", "oversized", "regular", "reta", "jogger", "skinny", "cargo", "wide leg", "cropped"),
    "construcao": ("bolso", "puffer", "gominho", "bomber", "corta vento", "peluciada", "texturizada", "rasgada", "destroyed"),
}

CURATION_DENY = ("feminino", "feminina", "infantil", "regata", "oversized", "plus", "short doll", "tactel", "poliamida", "praia")


def normalize(value):
    text = str(value or "").lower()
    replacements = {
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def title_case(value):
    fixed = " ".join(part.capitalize() for part in normalize(value).split())
    return (
        fixed.replace("Calca", "Calça")
        .replace("Sueter", "Suéter")
        .replace("Algodao Egipcio", "Algodão Egípcio")
        .replace("Cotele", "Cotelê")
        .replace("Pima Jersey", "Pima Jersey")
    )


def color_from_title(title):
    text = normalize(title)
    for color in COLORS:
        if normalize(color) in text:
            return title_case(color)
    parts = re.split(r"\s+-\s+", str(title or ""))
    fallback = title_case(parts[-1]) if len(parts) > 1 and len(parts[-1]) <= 22 else ""
    if not fallback or re.search(r"\d", fallback):
        return "Cor sob consulta"
    return fallback


def base_name(item):
    raw_title = str(item.get("title") or "")
    parts = re.split(r"\s+-\s+", raw_title)
    # O padrão do fornecedor é "modelo - cor - referência". A referência
    # às vezes chega truncada sem números (ex.: "cottx...") e, se for
    # normalizada junto, cria famílias falsas para a mesma peça.
    text = normalize(parts[0] if len(parts) >= 2 else raw_title)
    for color in COLORS:
        text = text.replace(normalize(color), " ")
    brand = normalize(item.get("brandLabel"))
    text = text.replace(brand, " ")
    tokens = [token for token in text.split() if token not in NOISE and not token.isdigit() and not re.search(r"\d", token)]
    return title_case(" ".join(tokens))


def material_key(item):
    text = normalize(f"{item.get('title')} {item.get('url')}")
    found = [normalize(term) for term in MATERIAL_TERMS if normalize(term) in text]
    return found[0] if found else ""


def signal_values(item, terms):
    # URL do catálogo contém "poa" no domínio; sinais visuais precisam vir
    # exclusivamente do nome da peça para não marcar todo o catálogo como poá.
    text = normalize(item.get("title"))
    return "+".join(term for term in terms if normalize(term) in text) or "nao-declarado"


def product_fingerprint(item):
    """Identidade mínima obrigatória antes de chamar algo de mesma peça."""
    title = normalize(item.get("title"))
    product_type = normalize(item.get("collection")) or next((term for term in ("camiseta", "polo", "camisa", "calca", "bermuda", "jaqueta", "sueter", "casaco") if term in title), "categoria-nao-declarada")
    return {
        "marca": normalize(item.get("brandLabel")) or "marca-nao-declarada",
        "categoria": product_type,
        "modelo": normalize(base_name(item)) or "modelo-nao-declarado",
        "malhaTecido": material_key(item) or "tecido-nao-declarado",
        "estampa": signal_values(item, STYLE_SIGNALS["estampa"]),
        "gola": signal_values(item, STYLE_SIGNALS["gola"]),
        "fechamento": signal_values(item, STYLE_SIGNALS["fechamento"]),
        "manga": signal_values(item, STYLE_SIGNALS["manga"]),
        "modelagem": signal_values(item, STYLE_SIGNALS["modelagem"]),
        "construcao": signal_values(item, STYLE_SIGNALS["construcao"]),
    }


def group_key(item):
    fingerprint = product_fingerprint(item)
    return "|".join(fingerprint.values())


def candidate_identity(item):
    """Chave estável para não repetir a mesma referência na curadoria."""
    supplier_id = normalize(item.get("supplierProductId"))
    if supplier_id:
        return f"id:{supplier_id}"
    url = str(item.get("url") or "").split("#", 1)[0].rstrip("/").lower()
    if url:
        return f"url:{url}"
    return f"fallback:{normalize(item.get('brandLabel'))}|{normalize(item.get('title'))}"


def eligible_for_curadoria(item):
    text = normalize(f"{item.get('title')} {item.get('url')} {item.get('categoryUrl')}")
    return not any(normalize(term) in text for term in CURATION_DENY)


def confidence_for_group(items):
    if len(items) < 2:
        return "individual"
    fingerprints = {tuple(sorted((item.get("fingerprint") or product_fingerprint(item)).items())) for item in items}
    if len(fingerprints) != 1:
        return "individual"

    # Títulos de fornecedor raramente dizem "lisa" ou descrevem todos os
    # detalhes visuais. Isso não deve espalhar 20 ou 40 cores/referências da
    # mesma família pelo painel. Quando marca, categoria e modelo coincidem,
    # mantemos a família junta; a falta de evidência visual reduz a confiança
    # para revisão humana, em vez de desfazer o grupo.
    only = items[0].get("fingerprint") or product_fingerprint(items[0])
    explicit_style = any(
        only.get(field) not in (None, "", "nao-declarado")
        for field in ("estampa", "gola", "fechamento", "manga", "modelagem", "construcao")
    )
    declared_material = only.get("malhaTecido") not in (None, "", "tecido-nao-declarado")
    return "alta" if explicit_style or declared_material else "revisar"


def group_items(candidates):
    grouped = defaultdict(list)
    seen_candidates = set()
    for item in candidates:
        if not eligible_for_curadoria(item):
            continue
        identity = candidate_identity(item)
        if identity in seen_candidates:
            continue
        seen_candidates.add(identity)
        enriched = dict(item)
        enriched["detectedColor"] = color_from_title(item.get("title"))
        enriched["baseName"] = base_name(item)
        enriched["fingerprint"] = product_fingerprint(item)
        enriched["groupKey"] = group_key(item)
        grouped[enriched["groupKey"]].append(enriched)

    groups = []
    singles = []
    for key, items in grouped.items():
        items.sort(key=lambda item: (item.get("detectedColor", ""), item.get("supplierProductId", "")))
        confidence = confidence_for_group(items)
        if confidence == "individual":
            singles.extend(items)
            continue
        representative = items[0]
        colors = sorted({item["detectedColor"] for item in items})
        sizes = sorted({size for item in items for size in (item.get("sizes") or [])}, key=lambda x: str(x))
        groups.append(
            {
                "id": "fornecedor-" + re.sub(r"[^a-z0-9]+", "-", key).strip("-")[:90],
                "groupKey": key,
                "status": confidence,
                "name": f"{representative.get('brandLabel')} - {representative.get('baseName')}",
                "brand": representative.get("brandLabel"),
                "collection": representative.get("collection"),
                "baseName": representative.get("baseName"),
                "fingerprint": representative.get("fingerprint"),
                "groupingRule": "Mesma marca, categoria, modelo e identidade declarada pelo fornecedor. Cor, tamanho e referência podem variar. Grupos sem evidência visual completa exigem revisão humana.",
                "colors": colors,
                "sizes": sizes,
                "count": len(items),
                "products": items,
            }
        )
    groups.sort(key=lambda item: (item["status"] != "alta", item["collection"], item["brand"], item["name"]))
    singles.sort(key=lambda item: (item.get("collection", ""), item.get("brandLabel", ""), item.get("title", "")))
    return groups, singles


def brand_label_for_site_product(product, brands):
    haystack = normalize(" ".join(str(value or "") for value in (
        product.get("name"),
        product.get("slug"),
        product.get("supplierGroupName"),
        product.get("supplierUrl"),
        product.get("internalNotes"),
        " ".join(product.get("tags") or []),
    )))
    for brand in brands:
        label = brand.get("label") or ""
        terms = [label, *(brand.get("terms") or []), *(brand.get("codes") or [])]
        if any(normalize(term) and normalize(term) in haystack for term in terms):
            return label
    return ""


def site_family_keys(products, brands):
    keys = set()
    for product in products:
        item = {
            "title": product.get("name"),
            "brandLabel": brand_label_for_site_product(product, brands),
            "collection": product.get("collection"),
            "url": product.get("supplierUrl"),
        }
        if item["brandLabel"]:
            keys.add(group_key(item))
    return keys


def apply_catalog_lanes(groups, singles, products, brands):
    existing_families = site_family_keys(products, brands)
    for group in groups:
        if group.get("status") == "revisar":
            group["lane"] = "revisar"
        elif group.get("groupKey") in existing_families:
            group["lane"] = "variacao-site"
        else:
            group["lane"] = "novidade"
    for item in singles:
        item["lane"] = "individual"
    return groups, singles


def esc(value):
    return _html.escape(str(value or ""))


def card(item, removable=False):
    product_id = str(item.get("supplierProductId") or item.get("url") or item.get("title") or "")
    action = (
        f'<button class="remove-item" type="button" data-remove-product="{esc(item.get("supplierProductId"))}">Excluir do grupo</button>'
        if removable
        else f'<label class="single-approval"><input type="checkbox" class="pick-single" value="single-{esc(product_id)}"> Aprovar peça</label>'
    )
    fingerprint = item.get("fingerprint") or product_fingerprint(item)
    identity = " · ".join(value for key, value in fingerprint.items() if key not in ("marca", "categoria") and value and value != "nao-declarado")
    return f"""
      <article class="product-card" data-id="{esc(item.get('supplierProductId'))}" data-approval-id="single-{esc(product_id)}">
        <img src="{esc(item.get('image'))}" alt="">
        <div>
          <strong>{esc(item.get('title'))}</strong>
          <span>{esc(item.get('brandLabel'))} | {esc(item.get('collection'))} | {esc(item.get('detectedColor'))}</span>
          <span><b>Identidade:</b> {esc(identity or 'sem evidência visual declarada / revisar foto')}</span>
          <span>Ref. {esc(item.get('supplierProductId'))} | tamanhos: {esc(', '.join(item.get('sizes') or []))}</span>
          <a href="{esc(item.get('url'))}" target="_blank" rel="noreferrer">Abrir fornecedor</a>
          {action}
        </div>
      </article>
    """


def write_grouped_preview(groups, singles, output_html, source_json, new_on_site=None):
    new_on_site = new_on_site or []
    ready_manifest_path = ROOT / "data" / "fornecedor-varreduras" / "fotos-prontas-site.json"
    ready_manifest = json.loads(ready_manifest_path.read_text(encoding="utf-8")) if ready_manifest_path.exists() else {"photos": {}}
    published_manifest_path = ROOT / "data" / "fornecedor-varreduras" / "fila-publicada-site.json"
    published_manifest = json.loads(published_manifest_path.read_text(encoding="utf-8")) if published_manifest_path.exists() else {"groups": []}
    if not new_on_site and published_manifest.get("groups"):
        new_on_site = [
            {
                "name": group.get("name"),
                "collection": group.get("collection"),
                "supplierProductId": f'{len(group.get("products", []))} peças',
            }
            for group in published_manifest.get("groups", [])
        ]
    published_ids = {
        str(product.get("supplierProductId") or "")
        for group in published_manifest.get("groups", [])
        for product in group.get("products", [])
    }
    visible_groups = []
    for source_group in groups:
        visible_products = [product for product in source_group.get("products", []) if str(product.get("supplierProductId") or "") not in published_ids]
        if not visible_products:
            continue
        group = dict(source_group)
        group["products"] = visible_products
        group["count"] = len(visible_products)
        group["colors"] = sorted({product.get("detectedColor") for product in visible_products if product.get("detectedColor")})
        group["sizes"] = sorted({size for product in visible_products for size in product.get("sizes", [])})
        visible_groups.append(group)
    groups = visible_groups
    singles = [product for product in singles if str(product.get("supplierProductId") or "") not in published_ids]
    data_json = json.dumps({"groups": groups, "individualCandidates": singles, "newOnSite": new_on_site, "readyPhotos": ready_manifest.get("photos", {}), "publishedQueue": published_manifest}, ensure_ascii=False).replace("</", "<\\/")
    brand_counts = Counter(group["brand"] for group in groups)
    collection_counts = Counter(group["collection"] for group in groups)
    lane_groups = defaultdict(list)
    for group in groups:
        representative = (group.get("products") or [{}])[0]
        lane_groups[group.get("lane") or "revisar"].append(
            f"""
            <article class="group" data-lane="{esc(group.get('lane'))}" data-status="{esc(group['status'])}" data-brand="{esc(group['brand'])}" data-collection="{esc(group['collection'])}">
              <header class="group-head">
                <img class="group-cover" src="{esc(representative.get('image'))}" alt="">
                <label><input type="checkbox" class="pick-group" value="{esc(group['id'])}"> Aprovar grupo</label>
                <div>
                  <span class="relation {esc(group.get('lane'))}">{esc({'novidade':'Nova família', 'variacao-site':'Nova variação', 'revisar':'Revisar identidade'}.get(group.get('lane'), 'Revisar'))}</span>
                  <h2>{esc(group['name'])}</h2>
                  <p><b>{esc(group['count'])} referências</b> · {esc(len(group['colors']))} cores · tamanhos {esc(', '.join(group['sizes']))}</p>
                  <p class="color-line">{esc(' · '.join(group['colors']))}</p>
                </div>
                <span class="status {esc(group['status'])}">{esc(group['status'])}</span>
              </header>
              <details class="variants"><summary>Ver e revisar as {esc(group['count'])} variações</summary><div class="products">{''.join(card(item, removable=True) for item in group['products'])}</div></details>
            </article>
            """
        )
    singles_html = "".join(card(item) for item in singles)
    lane_meta = (
        ("novidade", "01 · Novidades de verdade", "Famílias ainda não reconhecidas no catálogo atual. Prioridade para curadoria."),
        ("variacao-site", "02 · Novas variações do que já existe", "Novas cores ou referências de famílias que já estão no site."),
        ("revisar", "03 · Revisar identidade", "Parecem a mesma família, mas o fornecedor não descreve todos os detalhes visuais."),
    )
    lanes_html = "".join(
        f'<section class="lane-section" data-lane-section="{lane}"><header class="lane-head"><div><span>CURADORIA</span><h2>{title}</h2><p>{description}</p></div><strong>{len(lane_groups[lane])}</strong></header><div class="lane-grid">{"".join(lane_groups[lane]) or "<p>Nenhum item nesta área hoje.</p>"}</div></section>'
        for lane, title, description in lane_meta
    )
    site_news_html = "".join(
        f'<article><strong>{esc(item.get("name"))}</strong><span>{esc(item.get("collection"))} · Ref. {esc(item.get("supplierProductId") or "-")}</span></article>'
        for item in new_on_site
    ) or '<p>Nenhuma inclusão registrada desde a última varredura. O histórico automático começa a valer a partir desta versão.</p>'
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SCORSATTO - Pente fino fornecedor agrupado</title>
  <style>
    * {{ box-sizing: border-box; }}
    .hidden {{ display:none !important; }}
    body {{ margin:0; background:#f3f1eb; color:#181816; font-family:Inter,Arial,sans-serif; }}
    body, button, input, select, textarea {{ font: 14px Inter, Arial, sans-serif; }}
    .top {{ position: sticky; top: 0; z-index: 5; background:rgba(255,255,255,.96); backdrop-filter:blur(12px); border-bottom:1px solid #ddd8ce; padding:20px 28px; display:grid; gap:14px; }}
    .eyebrow {{ color:#706b61; font-size:10px; font-weight:900; letter-spacing:.18em; text-transform:uppercase; }}
    h1 {{ margin:3px 0 4px; font-family:Georgia,serif; font-size:30px; font-weight:500; }}
    h2 {{ margin:0 0 5px; font-size:16px; }}
    p {{ margin:0; color:#68635b; line-height:1.45; }}
    .view-tabs {{ display:flex; gap:8px; }}
    .view-tab {{ background:#fff; color:#111; border-color:#cfc8ba; }}
    .view-tab.active {{ background:#111; color:#fff; border-color:#111; }}
    .view-tab b {{ display:inline-grid; place-items:center; min-width:22px; height:22px; margin-left:6px; padding:0 6px; border-radius:999px; background:#e8d4a8; color:#111; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(180px,1fr) 190px 160px 160px; gap:10px; }}
    input[type="search"], select, textarea {{ width:100%; min-height:38px; border:1px solid #cfc8ba; border-radius:6px; background:#fff; padding:0 10px; }}
    button {{ min-height:38px; border:1px solid #111; border-radius:6px; background:#111; color:#fff; padding:0 12px; font-weight:800; cursor:pointer; }}
    button.secondary {{ background:#fff; color:#111; }}
    main {{ width:min(1480px,100%); margin:auto; padding:24px; display:grid; gap:24px; }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }}
    .metric {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; padding:14px; display:grid; gap:4px; }}
    .metric strong {{ font-size:22px; }}
    .lane-section {{ display:grid; gap:12px; }}
    .lane-section.hidden {{ display:none; }}
    .view-content.hidden {{ display:none; }}
    .lane-head {{ display:flex; align-items:end; justify-content:space-between; gap:20px; border-bottom:1px solid #cec8bd; padding:4px 2px 12px; }}
    .lane-head span {{ font-size:9px; font-weight:900; letter-spacing:.18em; }}
    .lane-head h2 {{ margin:4px 0; font-family:Georgia,serif; font-size:23px; font-weight:500; }}
    .lane-head strong {{ font-family:Georgia,serif; font-size:34px; font-weight:500; }}
    .lane-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .group {{ background:#fff; border:1px solid #ded8ce; border-radius:10px; overflow:hidden; box-shadow:0 8px 24px rgba(31,28,21,.035); }}
    .group.hidden {{ display:none; }}
    .group-head {{ display:grid; grid-template-columns:82px auto minmax(0,1fr) auto; align-items:center; gap:14px; padding:14px; }}
    .group-cover {{ width:82px; height:104px; object-fit:contain; background:#f6f3ec; border-radius:6px; }}
    .group-head label {{ display:flex; align-items:center; gap:8px; font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; }}
    .group-head input {{ width:18px; height:18px; accent-color:#111; }}
    .status {{ border:1px solid #d8d0c4; border-radius:999px; padding:5px 9px; font-size:11px; font-weight:900; text-transform:uppercase; }}
    .status.alta {{ background:#111; color:#fff; border-color:#111; }}
    .status.revisar {{ background:#fff9df; color:#5c4714; }}
    .relation {{ display:inline-block; margin-bottom:5px; font-size:9px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
    .relation.novidade {{ color:#764413; }} .relation.variacao-site {{ color:#24533d; }} .relation.revisar {{ color:#7a5d10; }}
    .color-line {{ font-size:11px; margin-top:4px; }}
    .variants {{ border-top:1px solid #ebe5dc; }}
    .variants summary {{ cursor:pointer; padding:12px 14px; font-size:11px; font-weight:900; text-transform:uppercase; letter-spacing:.06em; }}
    .products {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:1px; background:#ebe5dc; }}
    .product-card {{ background:#fff; padding:10px; display:grid; grid-template-columns:76px minmax(0,1fr); gap:10px; }}
    .product-card.excluded {{ opacity:.45; background:#f4eee6; }}
    .product-card.excluded img {{ filter: grayscale(1); }}
    .product-card img {{ width:76px; height:96px; object-fit:contain; background:#f8f6f0; }}
    .product-card div {{ display:grid; gap:5px; align-content:start; }}
    .product-card strong {{ font-size:12px; line-height:1.35; }}
    .product-card span, .product-card a {{ font-size:11px; line-height:1.4; color:#5f5b53; }}
    .product-card a {{ color:#111; font-weight:800; }}
    .remove-item {{ width:max-content; min-height:28px; border-color:#b9aa97; background:#fff; color:#251f17; padding:0 8px; font-size:10px; }}
    .single-approval {{ display:flex; align-items:center; gap:7px; margin-top:3px; font-size:10px; font-weight:900; text-transform:uppercase; }}
    .single-approval input {{ width:17px; height:17px; accent-color:#111; }}
    .product-card.excluded .remove-item {{ background:#111; border-color:#111; color:#fff; }}
    .panel {{ background:#fff; border:1px solid #ded8ce; border-radius:10px; padding:16px; display:grid; gap:12px; }}
    .approved-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .approved-card {{ background:#fff; border:1px solid #d8d0c4; border-radius:10px; overflow:hidden; }}
    .approved-card-head {{ display:grid; grid-template-columns:82px minmax(0,1fr); gap:14px; padding:14px; }}
    .approved-card-head img {{ width:82px; height:104px; object-fit:contain; background:#f6f3ec; border-radius:6px; }}
    .approved-card h3 {{ margin:5px 0; font-family:Georgia,serif; font-size:20px; font-weight:500; }}
    .pipeline {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:11px; }}
    .pipeline span {{ border:1px solid #d8d0c4; border-radius:999px; padding:5px 8px; color:#625e56; font-size:9px; font-weight:900; letter-spacing:.05em; text-transform:uppercase; }}
    .pipeline span:first-child {{ background:#fff4d5; border-color:#e5c976; color:#5a4312; }}
    .ready-card {{ border-color:#b8c9bc; }}
    .ready-card .pipeline span:first-child {{ background:#dcebdd; border-color:#9bbb9f; color:#214c2a; }}
    .published-card {{ border-color:#abc2b0; background:#fbfdfb; }}
    .published-card .pipeline span:first-child {{ background:#173c2a; border-color:#173c2a; color:#fff; }}
    .ready-card .product-card img {{ width:96px; height:120px; }}
    .ready-card .product-card {{ grid-template-columns:96px minmax(0,1fr); }}
    .approved-actions {{ display:flex; flex-wrap:wrap; gap:8px; padding:0 14px 14px; }}
    .approved-actions button {{ flex:1; }}
    .approved-products {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:1px; background:#ebe5dc; }}
    .empty-approved {{ padding:46px 20px; text-align:center; background:#fff; border:1px dashed #cfc8ba; border-radius:10px; }}
    .empty-approved h2 {{ font-family:Georgia,serif; font-size:26px; font-weight:500; }}
    .site-news {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:8px; }}
    .site-news article {{ display:grid; gap:5px; padding:12px; border:1px solid #e5dfd5; border-radius:7px; }}
    .site-news article span {{ color:#6e685e; font-size:11px; }}
    textarea {{ min-height:220px; padding:12px; font-family:Consolas,monospace; font-size:12px; }}
    @media (max-width: 980px) {{ .lane-grid,.approved-grid {{ grid-template-columns:1fr; }} .toolbar {{ grid-template-columns:1fr 1fr; }} .toolbar input[type="search"] {{ grid-column:1/-1; }} }}
    @media (max-width: 620px) {{ .group-head {{ grid-template-columns:68px 1fr; }} .group-cover {{ width:68px;height:88px; }} .group-head label,.group-head .status {{ grid-column:1/-1; }} main {{ padding:14px; }} }}
  </style>
</head>
<body>
  <section class="top">
    <div>
      <span class="eyebrow">SCORSATTO · RADAR DE CATÁLOGO</span>
      <h1>O que merece entrar.</h1>
      <p>Novidades separadas de variações existentes e dúvidas de identidade. Nada entra no site sem sua aprovação.</p>
    </div>
    <div class="view-tabs" role="tablist" aria-label="Etapas da curadoria">
      <button class="view-tab active" type="button" data-view="curation">Para escolher</button>
      <button class="view-tab" type="button" data-view="approved">Peças aprovadas <b id="approvedCount">0</b></button>
      <button class="view-tab" type="button" data-view="ready">Prontas para o site <b id="readyCount">0</b></button>
      <button class="view-tab" type="button" data-view="published">Já foram para o site <b id="publishedCount">0</b></button>
    </div>
    <div id="filtersToolbar" class="toolbar">
      <input id="searchBox" type="search" placeholder="Buscar grupo, marca, categoria ou cor">
      <select id="laneFilter"><option value="">Todas as áreas</option><option value="novidade">Novidades de verdade</option><option value="variacao-site">Variações do site</option><option value="revisar">Revisar identidade</option><option value="individual">Individuais</option></select>
      <select id="brandFilter"><option value="">Todas as marcas</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in brand_counts.most_common())}</select>
      <select id="collectionFilter"><option value="">Todas as categorias</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in collection_counts.most_common())}</select>
    </div>
  </section>
  <main>
    <div id="curationView" class="view-content">
    <section class="summary">
      <div class="metric"><strong>{len(lane_groups['novidade'])}</strong><span>Novas famílias</span></div>
      <div class="metric"><strong>{len(lane_groups['variacao-site'])}</strong><span>Variações do site</span></div>
      <div class="metric"><strong>{len(lane_groups['revisar'])}</strong><span>Famílias para revisar</span></div>
      <div class="metric"><strong>{len(singles)}</strong><span>Peças individuais</span></div>
    </section>
    <section class="panel">
      <span class="eyebrow">PUBLICADO · SITE SCORSATTO</span>
      <h2>O que entrou no site desde a última varredura</h2>
      <div class="site-news">{site_news_html}</div>
    </section>
    {lanes_html}
    <section class="lane-section" data-lane-section="individual"><header class="lane-head"><div><span>REVISÃO UNITÁRIA</span><h2>04 · Peças individuais</h2><p>Itens sem família segura. Ficam isolados para não misturar produtos diferentes.</p></div><strong>{len(singles)}</strong></header><details class="panel"><summary>Ver peças individuais</summary><div class="products">{singles_html}</div></details></section>
    </div>
    <section id="approvedView" class="view-content hidden">
      <header class="lane-head"><div><span>FILA DE PRODUÇÃO</span><h2>Peças aprovadas</h2><p>Grupos escolhidos por você. Agora seguem para foto padrão SCORSATTO e, depois, cadastro no site.</p></div><strong id="approvedHeadingCount">0</strong></header>
      <div id="approvedGrid" class="approved-grid"></div>
      <section class="panel">
        <h2>Fila pronta para produção</h2>
        <p>O arquivo abaixo preserva grupos, referências, cores, tamanhos e imagens do fornecedor para orientar as fotos sem trocar a peça real.</p>
        <button id="exportGroups" type="button">Baixar fila de fotos e site</button>
        <textarea id="exportBox" readonly placeholder="As peças aprovadas aparecem aqui."></textarea>
      </section>
    </section>
    <section id="readyView" class="view-content hidden">
      <header class="lane-head"><div><span>FILA FINAL</span><h2>Prontas para o site</h2><p>Grupos com todas as fotos padrão SCORSATTO concluídas. Confira peça por peça antes de liberar o cadastro no site.</p></div><strong id="readyHeadingCount">0</strong></header>
      <div id="readyGrid" class="approved-grid"></div>
    </section>
    <section id="publishedView" class="view-content hidden">
      <header class="lane-head"><div><span>CATÁLOGO OFICIAL</span><h2>Já foram para o site</h2><p>Histórico definitivo das peças publicadas, com o grupo usado no catálogo e acesso direto ao produto.</p></div><strong id="publishedHeadingCount">0</strong></header>
      <div id="publishedGrid" class="approved-grid"></div>
    </section>
  </main>
  <script id="group-data" type="application/json">{data_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById('group-data').textContent);
    const groups = payload.groups || [];
    const singles = (payload.individualCandidates || []).map(product => ({{
      id: 'single-' + String(product.supplierProductId || product.url || product.title),
      name: product.title,
      brand: product.brandLabel,
      collection: product.collection,
      lane: 'individual',
      status: 'individual',
      colors: [product.detectedColor].filter(Boolean),
      sizes: product.sizes || [],
      count: 1,
      products: [product]
    }}));
    const approvalItems = [...groups, ...singles];
    const readyPhotos = payload.readyPhotos || {{}};
    const publishedQueue = payload.publishedQueue || {{groups: []}};
    const publishedIds = new Set((publishedQueue.groups || []).flatMap(group => group.products || []).map(product => String(product.supplierProductId || '')));
    const byId = new Map(approvalItems.map(item => [item.id, item]));
    const queueKey = 'scorsatto-fila-fotos-aprovadas-v2';
    const excludedKey = 'scorsatto-fornecedor-grupos-excluidos-v2';
    const approvedQueue = JSON.parse(localStorage.getItem(queueKey) || '{{}}');
    const selected = new Set(Object.keys(approvedQueue));
    const excludedByGroup = JSON.parse(localStorage.getItem(excludedKey) || '{{}}');
    const cards = Array.from(document.querySelectorAll('.group'));
    const singleCards = Array.from(document.querySelectorAll('.product-card[data-approval-id]')).filter(card => card.querySelector('.pick-single'));
    const laneSections = Array.from(document.querySelectorAll('[data-lane-section]'));
    function escapeHtml(value) {{
      const entities = {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}};
      return String(value ?? '').replace(/[&<>"']/g, char => entities[char]);
    }}
    function saveQueue() {{ localStorage.setItem(queueKey, JSON.stringify(approvedQueue)); }}
    function saveExcluded() {{ localStorage.setItem(excludedKey, JSON.stringify(excludedByGroup)); }}
    function groupExcludedSet(groupId) {{
      excludedByGroup[groupId] = Array.isArray(excludedByGroup[groupId]) ? excludedByGroup[groupId] : [];
      return new Set(excludedByGroup[groupId]);
    }}
    function activeProducts(group) {{
      const excluded = groupExcludedSet(group.id);
      return (group.products || []).filter(product => !excluded.has(String(product.supplierProductId || product.url || product.title)));
    }}
    function snapshotForQueue(item) {{
      const products = activeProducts(item);
      return {{
        ...item,
        products,
        colors: [...new Set(products.map(product => product.detectedColor).filter(Boolean))],
        sizes: [...new Set(products.flatMap(product => product.sizes || []))],
        count: products.length,
        approvedAt: new Date().toISOString(),
        photoStatus: 'aguardando-foto-padrao-scorsatto',
        siteStatus: 'aguardando-fotos-e-cadastro'
      }};
    }}
    function renderApproved() {{
      const items = Object.values(approvedQueue).filter(item => !isReady(item));
      document.getElementById('approvedCount').textContent = items.length;
      document.getElementById('approvedHeadingCount').textContent = items.length;
      const grid = document.getElementById('approvedGrid');
      if (!items.length) {{
        grid.innerHTML = '<div class="empty-approved"><h2>Nenhuma peça aprovada ainda.</h2><p>Volte em “Para escolher” e aprove somente os grupos ou peças que você realmente quer vender.</p></div>';
        document.getElementById('exportBox').value = '';
        return;
      }}
      grid.innerHTML = items.map(item => {{
        const products = item.products || [];
        const cover = products[0]?.image || '';
        const productCards = products.map(product => `
          <article class="product-card">
            <img src="${{escapeHtml(product.image)}}" alt="">
            <div><strong>${{escapeHtml(product.title)}}</strong><span>${{escapeHtml(product.detectedColor || 'Cor sob consulta')}} · tamanhos: ${{escapeHtml((product.sizes || []).join(', '))}}</span><a href="${{escapeHtml(product.url)}}" target="_blank" rel="noreferrer">Conferir peça real</a></div>
          </article>`).join('');
        return `<article class="approved-card">
          <div class="approved-card-head"><img src="${{escapeHtml(cover)}}" alt=""><div><span class="eyebrow">APROVADA POR VOCÊ</span><h3>${{escapeHtml(item.name)}}</h3><p>${{escapeHtml(item.brand)}} · ${{escapeHtml(item.collection)}} · ${{products.length}} referência(s)</p><div class="pipeline"><span>Foto padrão pendente</span><span>Depois: cadastro no site</span></div></div></div>
          <details class="variants"><summary>Ver peças reais do grupo</summary><div class="approved-products">${{productCards}}</div></details>
          <div class="approved-actions"><button class="secondary" type="button" data-unapprove="${{escapeHtml(item.id)}}">Retirar da aprovação</button></div>
        </article>`;
      }}).join('');
    }}
    function isReady(item) {{
      const products = item.products || [];
      return products.length > 0 && products.every(product => readyPhotos[String(product.supplierProductId || '')]?.photo);
    }}
    function isPublished(item) {{
      const products = item.products || [];
      return products.length > 0 && products.every(product => publishedIds.has(String(product.supplierProductId || '')));
    }}
    function readyPhotoUrl(product) {{
      const path = readyPhotos[String(product.supplierProductId || '')]?.photo || '';
      return path ? '../../' + path : product.image;
    }}
    function renderReady() {{
      const items = Object.values(approvedQueue).filter(item => isReady(item) && !isPublished(item));
      document.getElementById('readyCount').textContent = items.length;
      document.getElementById('readyHeadingCount').textContent = items.length;
      const grid = document.getElementById('readyGrid');
      if (!items.length) {{
        grid.innerHTML = '<div class="empty-approved"><h2>Nenhum grupo com fotos completas.</h2><p>Quando todas as fotos de um grupo estiverem prontas, ele virá automaticamente para esta aba.</p></div>';
        return;
      }}
      grid.innerHTML = items.map(item => {{
        const products = item.products || [];
        const cover = readyPhotoUrl(products[0] || {{}});
        const productCards = products.map(product => `
          <article class="product-card">
            <img src="${{escapeHtml(readyPhotoUrl(product))}}" alt="Foto padrão SCORSATTO de ${{escapeHtml(product.title)}}">
            <div><strong>${{escapeHtml(product.title)}}</strong><span>${{escapeHtml(product.detectedColor || 'Cor sob consulta')}} · tamanhos: ${{escapeHtml((product.sizes || []).join(', '))}}</span><span><b>Foto padrão pronta</b> · revisão humana pendente</span><a href="${{escapeHtml(product.url)}}" target="_blank" rel="noreferrer">Comparar com a peça real</a></div>
          </article>`).join('');
        return `<article class="approved-card ready-card">
          <div class="approved-card-head"><img src="${{escapeHtml(cover)}}" alt=""><div><span class="eyebrow">FOTOS CONCLUÍDAS</span><h3>${{escapeHtml(item.name)}}</h3><p>${{escapeHtml(item.brand)}} · ${{escapeHtml(item.collection)}} · ${{products.length}} peça(s)</p><div class="pipeline"><span>Fotos prontas</span><span>Aguardando sua revisão</span><span>Depois: cadastro no site</span></div></div></div>
          <details class="variants" open><summary>Revisar as ${{products.length}} fotos do grupo</summary><div class="approved-products">${{productCards}}</div></details>
          <div class="approved-actions"><button class="secondary" type="button" data-unapprove="${{escapeHtml(item.id)}}">Retirar da aprovação</button></div>
        </article>`;
      }}).join('');
    }}
    function renderPublished() {{
      const items = publishedQueue.groups || [];
      document.getElementById('publishedCount').textContent = items.length;
      document.getElementById('publishedHeadingCount').textContent = items.length;
      const grid = document.getElementById('publishedGrid');
      if (!items.length) {{
        grid.innerHTML = '<div class="empty-approved"><h2>Nenhuma publicação registrada.</h2><p>Quando uma fila aprovada entrar no catálogo, o histórico aparecerá aqui.</p></div>';
        return;
      }}
      grid.innerHTML = items.map(item => {{
        const products = item.products || [];
        const cover = products[0]?.photo ? '../../' + products[0].photo : '';
        const action = item.siteGroupAction === 'merged-existing' ? 'Agrupada ao modelo existente' : 'Novo modelo criado';
        const productCards = products.map(product => `
          <article class="product-card">
            <img src="${{escapeHtml('../../' + product.photo)}}" alt="Foto de ${{escapeHtml(product.title)}}">
            <div><strong>${{escapeHtml(product.title)}}</strong><span>${{escapeHtml(product.color || '')}} · tamanhos: ${{escapeHtml((product.sizes || []).join(', '))}}</span><span><b>R$ ${{Number(product.price || 0).toFixed(2).replace('.', ',')}}</b> · publicado</span><a href="${{escapeHtml('../../' + product.siteUrl)}}" target="_blank" rel="noreferrer">Abrir no site</a></div>
          </article>`).join('');
        return `<article class="approved-card published-card">
          <div class="approved-card-head"><img src="${{escapeHtml(cover)}}" alt=""><div><span class="eyebrow">PUBLICADO NO SITE</span><h3>${{escapeHtml(item.name)}}</h3><p>${{escapeHtml(item.brand)}} · ${{products.length}} peça(s)</p><div class="pipeline"><span>No ar</span><span>${{escapeHtml(action)}}</span></div></div></div>
          <details class="variants"><summary>Ver peças publicadas</summary><div class="approved-products">${{productCards}}</div></details>
        </article>`;
      }}).join('');
    }}
    function setView(view) {{
      document.getElementById('curationView').classList.toggle('hidden', view !== 'curation');
      document.getElementById('approvedView').classList.toggle('hidden', view !== 'approved');
      document.getElementById('readyView').classList.toggle('hidden', view !== 'ready');
      document.getElementById('publishedView').classList.toggle('hidden', view !== 'published');
      document.getElementById('filtersToolbar').classList.toggle('hidden', view !== 'curation');
      document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === view));
      if (view === 'approved') renderApproved();
      if (view === 'ready') renderReady();
      if (view === 'published') renderPublished();
    }}
    function sync() {{
      const q = document.getElementById('searchBox').value.trim().toLowerCase();
      const lane = document.getElementById('laneFilter').value;
      const brand = document.getElementById('brandFilter').value;
      const collection = document.getElementById('collectionFilter').value;
      cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        const input = card.querySelector('.pick-group');
        const show = !selected.has(input.value) && (!q || text.includes(q)) && (!lane || card.dataset.lane === lane) && (!brand || card.dataset.brand === brand) && (!collection || card.dataset.collection === collection);
        card.classList.toggle('hidden', !show);
        input.checked = selected.has(input.value);
        const excluded = groupExcludedSet(input.value);
        card.querySelectorAll('.product-card').forEach(productCard => {{
          const id = String(productCard.dataset.id || '');
          const isExcluded = excluded.has(id);
          productCard.classList.toggle('excluded', isExcluded);
          const button = productCard.querySelector('[data-remove-product]');
          if (button) button.textContent = isExcluded ? 'Voltar para o grupo' : 'Excluir do grupo';
        }});
      }});
      singleCards.forEach(card => {{
        const input = card.querySelector('.pick-single');
        input.checked = selected.has(input.value);
        card.classList.toggle('hidden', selected.has(input.value));
      }});
      laneSections.forEach(section => {{
        if (section.dataset.laneSection === 'individual') {{
          section.classList.toggle('hidden', Boolean(lane && lane !== 'individual'));
          return;
        }}
        const hasVisibleGroup = Array.from(section.querySelectorAll('.group')).some(card => !card.classList.contains('hidden'));
        section.classList.toggle('hidden', !hasVisibleGroup);
      }});
      renderApproved();
      renderReady();
      renderPublished();
    }}
    document.querySelectorAll('.pick-group,.pick-single').forEach(input => input.addEventListener('change', () => {{
      const item = byId.get(input.value);
      if (input.checked && item) {{
        approvedQueue[input.value] = snapshotForQueue(item);
        selected.add(input.value);
      }} else {{
        delete approvedQueue[input.value];
        selected.delete(input.value);
      }}
      saveQueue();
      sync();
    }}));
    ['searchBox','laneFilter','brandFilter','collectionFilter'].forEach(id => document.getElementById(id).addEventListener('input', sync));
    document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
    document.addEventListener('click', event => {{
      const unapprove = event.target.closest('[data-unapprove]');
      if (unapprove) {{
        delete approvedQueue[unapprove.dataset.unapprove];
        selected.delete(unapprove.dataset.unapprove);
        saveQueue();
        sync();
        renderApproved();
        renderReady();
        return;
      }}
      const button = event.target.closest('[data-remove-product]');
      if (!button) return;
      const groupEl = button.closest('.group');
      const input = groupEl?.querySelector('.pick-group');
      if (!input) return;
      const groupId = input.value;
      const productId = String(button.dataset.removeProduct || '');
      const excluded = groupExcludedSet(groupId);
      if (excluded.has(productId)) excluded.delete(productId);
      else excluded.add(productId);
      excludedByGroup[groupId] = [...excluded];
      saveExcluded();
      if (selected.has(groupId)) approvedQueue[groupId] = snapshotForQueue(byId.get(groupId));
      saveQueue();
      sync();
    }});
    document.getElementById('exportGroups').addEventListener('click', () => {{
      const approvedGroups = Object.values(approvedQueue).filter(group => (group.products || []).length >= 1);
      const exportPayload = {{
        generatedAt: new Date().toISOString(),
        workflow: ['aprovado-pelo-Alisson', 'criar-fotos-padrao-scorsatto-com-a-peca-real', 'revisao-humana-das-fotos', 'cadastrar-no-site'],
        rule: 'Nunca trocar a peça real. Fotos e cadastro no site exigem revisão humana.',
        approvedGroupCount: approvedGroups.length,
        approvedGroups
      }};
      const json = JSON.stringify(exportPayload, null, 2);
      document.getElementById('exportBox').value = json;
      const blobUrl = URL.createObjectURL(new Blob([json], {{type:'application/json'}}));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = 'fila-fotos-site-scorsatto.json';
      link.click();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    }});
    sync();
  </script>
</body>
</html>"""
    clean_html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    output_html.write_text(clean_html, encoding="utf-8")


def main():
    day = today_slug()
    source = ROOT / "data" / "fornecedor-varreduras" / f"varredura-fornecedor-{day}.json"
    if not source.exists():
        available = sorted((ROOT / "data" / "fornecedor-varreduras").glob("varredura-fornecedor-????-??-??.json"))
        if not available:
            raise RuntimeError(f"Varredura nao encontrada: {source}")
        source = available[-1]
        day = source.stem.removeprefix("varredura-fornecedor-")
    data = json.loads(source.read_text(encoding="utf-8"))
    candidates = data.get("candidates") or []
    groups, singles = group_items(candidates)
    products, _, _ = parse_products_from_index()
    _, brands = parse_site_taxonomy()
    groups, singles = apply_catalog_lanes(groups, singles, products, brands)
    new_on_site = data.get("newOnSite") or []
    out_dir = ROOT / "previews" / "fornecedor-varreduras"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = ROOT / "data" / "fornecedor-varreduras" / f"varredura-fornecedor-agrupada-{day}.json"
    html_path = out_dir / f"aprovacao-fornecedor-agrupado-{day}.html"
    payload = {
        "generatedAt": data.get("generatedAt"),
        "source": str(source),
        "groupCount": len(groups),
        "highConfidenceGroupCount": sum(1 for group in groups if group["status"] == "alta"),
        "groupedProductCount": sum(group["count"] for group in groups),
        "individualCount": len(singles),
        "newFamilyCount": sum(1 for group in groups if group.get("lane") == "novidade"),
        "existingFamilyVariationCount": sum(1 for group in groups if group.get("lane") == "variacao-site"),
        "reviewGroupCount": sum(1 for group in groups if group.get("lane") == "revisar"),
        "newOnSite": new_on_site,
        "groups": groups,
        "individualCandidates": singles,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_grouped_preview(groups, singles, html_path, source.name, new_on_site=new_on_site)
    # Endereço estável para a operação: sempre aponta para a varredura mais recente.
    write_grouped_preview(groups, singles, out_dir / "index.html", source.name, new_on_site=new_on_site)
    print(json.dumps({"groups": len(groups), "highConfidence": payload["highConfidenceGroupCount"], "groupedProducts": payload["groupedProductCount"], "individual": len(singles), "json": str(json_path), "preview": str(html_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
