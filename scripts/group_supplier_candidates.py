import html as _html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from supplier_common import ROOT, today_slug


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
    text = normalize(item.get("title"))
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


def group_key(item):
    return "|".join(
        [
            normalize(item.get("brandLabel")),
            normalize(item.get("collection")),
            normalize(base_name(item)),
            material_key(item),
        ]
    )


def confidence_for_group(items):
    if len(items) < 2:
        return "individual"
    brands = {item.get("brandLabel") for item in items}
    collections = {item.get("collection") for item in items}
    bases = {base_name(item) for item in items}
    materials = {material_key(item) for item in items}
    colors = {color_from_title(item.get("title")) for item in items}
    if len(brands) == len(collections) == len(bases) == 1 and len(colors) >= 1:
        return "alta"
    if len(brands) == 1 and len(collections) == 1 and len(materials) <= 2:
        return "revisar"
    return "individual"


def group_items(candidates):
    grouped = defaultdict(list)
    for item in candidates:
        enriched = dict(item)
        enriched["detectedColor"] = color_from_title(item.get("title"))
        enriched["baseName"] = base_name(item)
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
                "status": confidence,
                "name": f"{representative.get('brandLabel')} - {representative.get('baseName')}",
                "brand": representative.get("brandLabel"),
                "collection": representative.get("collection"),
                "baseName": representative.get("baseName"),
                "colors": colors,
                "sizes": sizes,
                "count": len(items),
                "products": items,
            }
        )
    groups.sort(key=lambda item: (item["status"] != "alta", item["collection"], item["brand"], item["name"]))
    singles.sort(key=lambda item: (item.get("collection", ""), item.get("brandLabel", ""), item.get("title", "")))
    return groups, singles


def esc(value):
    return _html.escape(str(value or ""))


def card(item, removable=False):
    action = (
        f'<button class="remove-item" type="button" data-remove-product="{esc(item.get("supplierProductId"))}">Excluir do grupo</button>'
        if removable
        else ""
    )
    return f"""
      <article class="product-card" data-id="{esc(item.get('supplierProductId'))}">
        <img src="{esc(item.get('image'))}" alt="">
        <div>
          <strong>{esc(item.get('title'))}</strong>
          <span>{esc(item.get('brandLabel'))} | {esc(item.get('collection'))} | {esc(item.get('detectedColor'))}</span>
          <span>Ref. {esc(item.get('supplierProductId'))} | tamanhos: {esc(', '.join(item.get('sizes') or []))}</span>
          <a href="{esc(item.get('url'))}" target="_blank" rel="noreferrer">Abrir fornecedor</a>
          {action}
        </div>
      </article>
    """


def write_grouped_preview(groups, singles, output_html, source_json):
    data_json = json.dumps({"groups": groups, "individualCandidates": singles}, ensure_ascii=False).replace("</", "<\\/")
    brand_counts = Counter(group["brand"] for group in groups)
    collection_counts = Counter(group["collection"] for group in groups)
    group_html = []
    for group in groups:
        group_html.append(
            f"""
            <section class="group" data-status="{esc(group['status'])}" data-brand="{esc(group['brand'])}" data-collection="{esc(group['collection'])}">
              <header class="group-head">
                <label><input type="checkbox" class="pick-group" value="{esc(group['id'])}"> Aprovar grupo</label>
                <div>
                  <h2>{esc(group['name'])}</h2>
                  <p>{esc(group['count'])} referencias | cores: {esc(', '.join(group['colors']))} | tamanhos: {esc(', '.join(group['sizes']))}</p>
                </div>
                <span class="status {esc(group['status'])}">{esc(group['status'])}</span>
              </header>
              <div class="products">{''.join(card(item, removable=True) for item in group['products'])}</div>
            </section>
            """
        )
    singles_html = "".join(card(item) for item in singles)
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SCORSATTO - Pente fino fornecedor agrupado</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:#f7f5ef; color:#181816; font-family:Inter,Arial,sans-serif; }}
    body, button, input, select, textarea {{ font: 14px Inter, Arial, sans-serif; }}
    .top {{ position: sticky; top: 0; z-index: 5; background:#fff; border-bottom:1px solid #ddd8ce; padding:20px 28px; display:grid; gap:14px; }}
    h1 {{ margin:0; font-size:24px; }}
    h2 {{ margin:0 0 5px; font-size:16px; }}
    p {{ margin:0; color:#68635b; line-height:1.45; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(180px,1fr) 180px 180px auto auto; gap:10px; }}
    input[type="search"], select, textarea {{ width:100%; min-height:38px; border:1px solid #cfc8ba; border-radius:6px; background:#fff; padding:0 10px; }}
    button {{ min-height:38px; border:1px solid #111; border-radius:6px; background:#111; color:#fff; padding:0 12px; font-weight:800; cursor:pointer; }}
    button.secondary {{ background:#fff; color:#111; }}
    main {{ padding:22px; display:grid; gap:18px; }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }}
    .metric {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; padding:14px; display:grid; gap:4px; }}
    .metric strong {{ font-size:22px; }}
    .group {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; overflow:hidden; }}
    .group.hidden {{ display:none; }}
    .group-head {{ display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:14px; padding:14px; border-bottom:1px solid #ebe5dc; }}
    .group-head label {{ display:flex; align-items:center; gap:8px; font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; }}
    .group-head input {{ width:18px; height:18px; accent-color:#111; }}
    .status {{ border:1px solid #d8d0c4; border-radius:999px; padding:5px 9px; font-size:11px; font-weight:900; text-transform:uppercase; }}
    .status.alta {{ background:#111; color:#fff; border-color:#111; }}
    .status.revisar {{ background:#fff9df; color:#5c4714; }}
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
    .panel {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; padding:14px; display:grid; gap:12px; }}
    textarea {{ min-height:220px; padding:12px; font-family:Consolas,monospace; font-size:12px; }}
    @media (max-width: 860px) {{ .toolbar {{ grid-template-columns:1fr 1fr; }} .toolbar input[type="search"] {{ grid-column:1/-1; }} .group-head {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <section class="top">
    <div>
      <h1>Pente fino fornecedor agrupado</h1>
      <p>{len(groups)} grupos sugeridos e {len(singles)} candidatos individuais. Nada foi inserido no site. Fonte: {esc(source_json)}</p>
    </div>
    <div class="toolbar">
      <input id="searchBox" type="search" placeholder="Buscar grupo, marca, categoria ou cor">
      <select id="brandFilter"><option value="">Todas as marcas</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in brand_counts.most_common())}</select>
      <select id="collectionFilter"><option value="">Todas as categorias</option>{''.join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>' for k, v in collection_counts.most_common())}</select>
      <button id="selectHigh" type="button">Selecionar alta confiança</button>
      <button id="exportGroups" type="button">Exportar aprovados</button>
    </div>
  </section>
  <main>
    <section class="summary">
      <div class="metric"><strong>{len(groups)}</strong><span>Grupos sugeridos</span></div>
      <div class="metric"><strong>{sum(1 for g in groups if g['status'] == 'alta')}</strong><span>Alta confiança</span></div>
      <div class="metric"><strong>{sum(group['count'] for group in groups)}</strong><span>Referências agrupáveis</span></div>
      <div class="metric"><strong>{len(singles)}</strong><span>Individuais/revisar depois</span></div>
    </section>
    {''.join(group_html) if group_html else '<p>Nenhum grupo sugerido.</p>'}
    <section class="panel">
      <h2>Individuais e baixa confiança</h2>
      <p>Esses itens ficaram fora dos grupos porque poderiam misturar peças diferentes ou precisam de decisão manual.</p>
      <div class="products">{singles_html}</div>
    </section>
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
      const brand = document.getElementById('brandFilter').value;
      const collection = document.getElementById('collectionFilter').value;
      cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        const show = (!q || text.includes(q)) && (!brand || card.dataset.brand === brand) && (!collection || card.dataset.collection === collection);
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
    }}
    document.querySelectorAll('.pick-group').forEach(input => input.addEventListener('change', () => {{
      if (input.checked) selected.add(input.value);
      else selected.delete(input.value);
      save();
      sync();
    }}));
    ['searchBox','brandFilter','collectionFilter'].forEach(id => document.getElementById(id).addEventListener('input', sync));
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
      const json = JSON.stringify(exportPayload, null, 2);
      document.getElementById('exportBox').value = json;
      const blob = new Blob([json], {{ type: 'application/json' }});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'scorsatto-grupos-aprovados-para-fotos-{today_slug()}.json';
      link.click();
      URL.revokeObjectURL(link.href);
    }});
    sync();
  </script>
</body>
</html>"""
    output_html.write_text(html, encoding="utf-8")


def main():
    day = today_slug()
    source = ROOT / "data" / "fornecedor-varreduras" / f"varredura-fornecedor-{day}.json"
    if not source.exists():
        candidates = sorted((ROOT / "data" / "fornecedor-varreduras").glob("varredura-fornecedor-*.json"))
        candidates = [path for path in candidates if "agrupada" not in path.name]
        if not candidates:
            raise RuntimeError(f"Varredura nao encontrada: {source}")
        source = candidates[-1]
        day = source.stem.replace("varredura-fornecedor-", "")
    data = json.loads(source.read_text(encoding="utf-8"))
    candidates = data.get("candidates") or []
    groups, singles = group_items(candidates)
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
        "groups": groups,
        "individualCandidates": singles,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_grouped_preview(groups, singles, html_path, source.name)
    print(json.dumps({"groups": len(groups), "highConfidence": payload["highConfidenceGroupCount"], "groupedProducts": payload["groupedProductCount"], "individual": len(singles), "json": str(json_path), "preview": str(html_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
