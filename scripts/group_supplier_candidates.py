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
    action = (
        f'<button class="remove-item" type="button" data-remove-product="{esc(item.get("supplierProductId"))}">Excluir do grupo</button>'
        if removable
        else ""
    )
    fingerprint = item.get("fingerprint") or product_fingerprint(item)
    identity = " · ".join(value for key, value in fingerprint.items() if key not in ("marca", "categoria") and value and value != "nao-declarado")
    return f"""
      <article class="product-card" data-id="{esc(item.get('supplierProductId'))}">
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
    data_json = json.dumps({"groups": groups, "individualCandidates": singles, "newOnSite": new_on_site}, ensure_ascii=False).replace("</", "<\\/")
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
    body {{ margin:0; background:#f3f1eb; color:#181816; font-family:Inter,Arial,sans-serif; }}
    body, button, input, select, textarea {{ font: 14px Inter, Arial, sans-serif; }}
    .top {{ position: sticky; top: 0; z-index: 5; background:rgba(255,255,255,.96); backdrop-filter:blur(12px); border-bottom:1px solid #ddd8ce; padding:20px 28px; display:grid; gap:14px; }}
    .eyebrow {{ color:#706b61; font-size:10px; font-weight:900; letter-spacing:.18em; text-transform:uppercase; }}
    h1 {{ margin:3px 0 4px; font-family:Georgia,serif; font-size:30px; font-weight:500; }}
    h2 {{ margin:0 0 5px; font-size:16px; }}
    p {{ margin:0; color:#68635b; line-height:1.45; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(180px,1fr) 190px 160px 160px auto auto; gap:10px; }}
    input[type="search"], select, textarea {{ width:100%; min-height:38px; border:1px solid #cfc8ba; border-radius:6px; background:#fff; padding:0 10px; }}
    button {{ min-height:38px; border:1px solid #111; border-radius:6px; background:#111; color:#fff; padding:0 12px; font-weight:800; cursor:pointer; }}
    button.secondary {{ background:#fff; color:#111; }}
    main {{ width:min(1480px,100%); margin:auto; padding:24px; display:grid; gap:24px; }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }}
    .metric {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; padding:14px; display:grid; gap:4px; }}
    .metric strong {{ font-size:22px; }}
    .lane-section {{ display:grid; gap:12px; }}
    .lane-section.hidden {{ display:none; }}
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
    .product-card.excluded .remove-item {{ background:#111; border-color:#111; color:#fff; }}
    .panel {{ background:#fff; border:1px solid #ded8ce; border-radius:10px; padding:16px; display:grid; gap:12px; }}
    .site-news {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:8px; }}
    .site-news article {{ display:grid; gap:5px; padding:12px; border:1px solid #e5dfd5; border-radius:7px; }}
    .site-news article span {{ color:#6e685e; font-size:11px; }}
    textarea {{ min-height:220px; padding:12px; font-family:Consolas,monospace; font-size:12px; }}
    @media (max-width: 980px) {{ .lane-grid {{ grid-template-columns:1fr; }} .toolbar {{ grid-template-columns:1fr 1fr; }} .toolbar input[type="search"] {{ grid-column:1/-1; }} }}
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
    <div class="toolbar">
      <input id="searchBox" type="search" placeholder="Buscar grupo, marca, categoria ou cor">
      <select id="laneFilter"><option value="">Todas as áreas</option><option value="novidade">Novidades de verdade</option><option value="variacao-site">Variações do site</option><option value="revisar">Revisar identidade</option><option value="individual">Individuais</option></select>
      <select id="brandFilter"><option value="">Todas as marcas</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in brand_counts.most_common())}</select>
      <select id="collectionFilter"><option value="">Todas as categorias</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in collection_counts.most_common())}</select>
      <button id="selectHigh" type="button">Selecionar alta confiança</button>
      <button id="exportGroups" type="button">Exportar aprovados</button>
    </div>
  </section>
  <main>
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
    <section class="panel">
      <h2>Exportação para aprovação</h2>
      <textarea id="exportBox" readonly placeholder="Os grupos aprovados aparecem aqui."></textarea>
    </section>
  </main>
  <script id="group-data" type="application/json">{data_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById('group-data').textContent);
    const groups = payload.groups || [];
    const byId = new Map(groups.map(group => [group.id, group]));
    const storageKey = 'scorsatto-fornecedor-grupos-aprovados-' + location.pathname;
    const excludedKey = 'scorsatto-fornecedor-grupos-excluidos-' + location.pathname;
    const selected = new Set(JSON.parse(localStorage.getItem(storageKey) || '[]'));
    const excludedByGroup = JSON.parse(localStorage.getItem(excludedKey) || '{{}}');
    const cards = Array.from(document.querySelectorAll('.group'));
    const laneSections = Array.from(document.querySelectorAll('[data-lane-section]'));
    function save() {{ localStorage.setItem(storageKey, JSON.stringify([...selected])); }}
    function saveExcluded() {{ localStorage.setItem(excludedKey, JSON.stringify(excludedByGroup)); }}
    function groupExcludedSet(groupId) {{
      excludedByGroup[groupId] = Array.isArray(excludedByGroup[groupId]) ? excludedByGroup[groupId] : [];
      return new Set(excludedByGroup[groupId]);
    }}
    function activeProducts(group) {{
      const excluded = groupExcludedSet(group.id);
      return (group.products || []).filter(product => !excluded.has(String(product.supplierProductId || product.url || product.title)));
    }}
    function sync() {{
      const q = document.getElementById('searchBox').value.trim().toLowerCase();
      const lane = document.getElementById('laneFilter').value;
      const brand = document.getElementById('brandFilter').value;
      const collection = document.getElementById('collectionFilter').value;
      cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        const show = (!q || text.includes(q)) && (!lane || card.dataset.lane === lane) && (!brand || card.dataset.brand === brand) && (!collection || card.dataset.collection === collection);
        card.classList.toggle('hidden', !show);
        const input = card.querySelector('.pick-group');
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
      laneSections.forEach(section => {{
        if (section.dataset.laneSection === 'individual') {{
          section.classList.toggle('hidden', Boolean(lane && lane !== 'individual'));
          return;
        }}
        const hasVisibleGroup = Array.from(section.querySelectorAll('.group')).some(card => !card.classList.contains('hidden'));
        section.classList.toggle('hidden', !hasVisibleGroup);
      }});
    }}
    document.querySelectorAll('.pick-group').forEach(input => input.addEventListener('change', () => {{
      if (input.checked) selected.add(input.value);
      else selected.delete(input.value);
      save();
      sync();
    }}));
    ['searchBox','laneFilter','brandFilter','collectionFilter'].forEach(id => document.getElementById(id).addEventListener('input', sync));
    document.getElementById('selectHigh').addEventListener('click', () => {{
      groups.filter(group => group.status === 'alta').forEach(group => selected.add(group.id));
      save();
      sync();
    }});
    document.addEventListener('click', event => {{
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
      sync();
    }});
    document.getElementById('exportGroups').addEventListener('click', () => {{
      const approvedGroups = [...selected].map(id => byId.get(id)).filter(Boolean).map(group => {{
        const products = activeProducts(group);
        const colors = [...new Set(products.map(product => product.detectedColor).filter(Boolean))];
        const sizes = [...new Set(products.flatMap(product => product.sizes || []))];
        return {{ ...group, products, colors, sizes, count: products.length, excludedProductIds: excludedByGroup[group.id] || [] }};
      }}).filter(group => group.products.length >= 2);
      const exportPayload = {{
        generatedAt: new Date().toISOString(),
        rule: 'Aprovado pelo Alisson antes de inserir no site. Agrupar somente mesma marca, mesma categoria e mesma peca; cores e tamanhos como variacoes.',
        approvedGroupCount: approvedGroups.length,
        approvedGroups
      }};
      document.getElementById('exportBox').value = JSON.stringify(exportPayload, null, 2);
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
        raise RuntimeError(f"Varredura nao encontrada: {source}")
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
