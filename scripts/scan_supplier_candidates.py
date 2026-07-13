import html as _html
import json
from pathlib import Path

from supplier_common import (
    ROOT,
    clean_text,
    discover_relevant_category_urls,
    enrich_supplier_item,
    existing_supplier_ids,
    existing_supplier_urls,
    fetch_text,
    is_scorsatto_candidate,
    now_iso,
    parse_listing_products,
    parse_products_from_index,
    parse_site_taxonomy,
    today_slug,
)


def scan_category(url, max_pages=6):
    found = []
    seen = set()
    for page in range(1, max_pages + 1):
        page_url = url if page == 1 else f"{url}?page={page}"
        html = fetch_text(page_url)
        items = parse_listing_products(html, page_url)
        if not items:
            break
        before = len(found)
        for item in items:
            key = item["url"]
            if key not in seen:
                item["categoryUrl"] = url
                found.append(item)
                seen.add(key)
        if len(found) == before:
            break
    return found


def option_tags(values, labels=None):
    labels = labels or {}
    tags = ['<option value="">Todos</option>']
    for value in values:
        label = labels.get(value, value)
        tags.append(f'<option value="{_html.escape(value)}">{_html.escape(label)}</option>')
    return "".join(tags)


def write_preview(candidates, output_html, categories=None, title="Varredura fornecedor - candidatos para aprovacao"):
    categories = categories or []
    category_labels = {c.get("collection"): c.get("label") for c in categories if c.get("collection")}
    brand_values = sorted({item.get("brandLabel") or "Sem marca" for item in candidates})
    collection_values = sorted({item.get("collection") or "sem-categoria" for item in candidates})
    data_json = json.dumps(candidates, ensure_ascii=False).replace("</", "<\\/")
    cards = []
    for item in candidates:
        item_id = str(item.get("supplierProductId") or item.get("url") or item.get("title"))
        sizes = ", ".join(item.get("sizes") or [])
        brand = item.get("brandLabel") or "Sem marca"
        collection = item.get("collection") or "sem-categoria"
        title_text = clean_text(item.get("title", ""))
        cards.append(
            f"""
            <article class="card" data-id="{_html.escape(item_id)}" data-brand="{_html.escape(brand)}" data-collection="{_html.escape(collection)}" data-search="{_html.escape((title_text + ' ' + brand + ' ' + collection).lower())}">
              <label class="select-line">
                <input type="checkbox" class="pick" value="{_html.escape(item_id)}">
                <span>Selecionar para aprovacao</span>
              </label>
              <img src="{_html.escape(item.get('image',''))}" alt="">
              <div class="body">
                <div class="badges"><span>{_html.escape(brand)}</span><span>{_html.escape(category_labels.get(collection, collection))}</span></div>
                <strong>{_html.escape(title_text)}</strong>
                <span>Ref. {_html.escape(str(item.get('supplierProductId','')))} | tamanhos: {_html.escape(sizes or '-')}</span>
                <span>Atacado: R$ {_html.escape(item.get('wholesalePrice') or '-')} | Varejo: R$ {_html.escape(item.get('retailPrice') or '-')}</span>
                <a href="{_html.escape(item.get('url',''))}" target="_blank" rel="noreferrer">Abrir fornecedor</a>
              </div>
            </article>
            """
        )
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SCORSATTO - {title}</title>
  <style>
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f7f5ef; color:#181816; font-family:Inter,Arial,sans-serif; }}
    header {{ padding:22px 32px; background:#fff; border-bottom:1px solid #ddd8ce; position:sticky; top:0; z-index:2; display:grid; gap:14px; }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    p {{ margin:0; color:#666; }}
    .toolbar {{ display:grid; grid-template-columns:minmax(180px,1fr) 180px 180px auto auto auto; gap:10px; align-items:center; }}
    input[type="search"], select, textarea {{ width:100%; min-height:38px; border:1px solid #cfc8ba; border-radius:6px; background:#fff; padding:0 10px; font:inherit; }}
    main {{ padding:24px; display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px; }}
    .card {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; overflow:hidden; display:grid; position:relative; }}
    .card.selected {{ border-color:#111; box-shadow:0 0 0 2px #111 inset; }}
    .card.hidden {{ display:none; }}
    .select-line {{ display:flex; align-items:center; gap:8px; padding:10px 12px; border-bottom:1px solid #ece7df; font-size:12px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; cursor:pointer; }}
    .select-line input {{ width:18px; height:18px; accent-color:#111; }}
    img {{ width:100%; aspect-ratio:1/1; object-fit:contain; background:#f8f6f0; }}
    .body {{ padding:14px; display:grid; gap:8px; }}
    .badges {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .badges span {{ border:1px solid #ddd6ca; border-radius:999px; padding:4px 8px; background:#faf8f2; color:#34312b; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }}
    strong {{ font-size:14px; line-height:1.35; }}
    span, a {{ font-size:12px; color:#5f5b53; }}
    a {{ color:#111; font-weight:700; }}
    button {{ border:1px solid #111; border-radius:6px; background:#111; color:#fff; min-height:38px; padding:0 12px; font-weight:800; cursor:pointer; }}
    button.secondary {{ background:#fff; color:#111; }}
    .export-panel {{ display:none; padding:0 24px 24px; }}
    .export-panel.open {{ display:block; }}
    textarea {{ min-height:160px; padding:12px; font-family:Consolas,monospace; font-size:12px; }}
    .count {{ font-weight:800; color:#181816; }}
    @media (max-width: 820px) {{ .toolbar {{ grid-template-columns:1fr 1fr; }} .toolbar input[type="search"] {{ grid-column:1 / -1; }} }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{_html.escape(title)}</h1>
      <p><span class="count" id="visibleCount">{len(candidates)}</span> de {len(candidates)} pecas novas na tela. Selecionadas: <span class="count" id="selectedCount">0</span>. Nada foi inserido no site.</p>
    </div>
    <div class="toolbar">
      <input id="searchBox" type="search" placeholder="Buscar peca, marca ou categoria">
      <select id="brandFilter" aria-label="Filtrar marca">{option_tags(brand_values)}</select>
      <select id="collectionFilter" aria-label="Filtrar categoria">{option_tags(collection_values, category_labels)}</select>
      <button id="selectVisible" type="button">Selecionar visiveis</button>
      <button id="clearSelection" class="secondary" type="button">Limpar</button>
      <button id="exportSelection" type="button">Exportar selecionadas</button>
    </div>
  </header>
  <main>{''.join(cards) if cards else '<p>Nenhuma peca nova encontrada nesta varredura.</p>'}</main>
  <section id="exportPanel" class="export-panel">
    <textarea id="exportBox" readonly placeholder="As pecas aprovadas aparecem aqui em JSON para inserir depois da aprovacao."></textarea>
  </section>
  <script id="candidate-data" type="application/json">{data_json}</script>
  <script>
    const candidates = JSON.parse(document.getElementById('candidate-data').textContent);
    const byId = new Map(candidates.map(item => [String(item.supplierProductId || item.url || item.title), item]));
    const storageKey = 'scorsatto-fornecedor-selecao-' + location.pathname;
    const selected = new Set(JSON.parse(localStorage.getItem(storageKey) || '[]'));
    const cards = Array.from(document.querySelectorAll('.card'));
    const checks = Array.from(document.querySelectorAll('.pick'));
    const searchBox = document.getElementById('searchBox');
    const brandFilter = document.getElementById('brandFilter');
    const collectionFilter = document.getElementById('collectionFilter');
    const visibleCount = document.getElementById('visibleCount');
    const selectedCount = document.getElementById('selectedCount');
    const exportPanel = document.getElementById('exportPanel');
    const exportBox = document.getElementById('exportBox');

    function save() {{
      localStorage.setItem(storageKey, JSON.stringify(Array.from(selected)));
    }}
    function syncCards() {{
      let visible = 0;
      const query = searchBox.value.trim().toLowerCase();
      const brand = brandFilter.value;
      const collection = collectionFilter.value;
      cards.forEach(card => {{
        const id = card.dataset.id;
        const isSelected = selected.has(id);
        const isVisible = (!query || card.dataset.search.includes(query)) && (!brand || card.dataset.brand === brand) && (!collection || card.dataset.collection === collection);
        card.classList.toggle('selected', isSelected);
        card.classList.toggle('hidden', !isVisible);
        card.querySelector('.pick').checked = isSelected;
        if (isVisible) visible += 1;
      }});
      visibleCount.textContent = visible;
      selectedCount.textContent = selected.size;
    }}
    checks.forEach(check => {{
      check.addEventListener('change', () => {{
        if (check.checked) selected.add(check.value);
        else selected.delete(check.value);
        save();
        syncCards();
      }});
    }});
    [searchBox, brandFilter, collectionFilter].forEach(control => control.addEventListener('input', syncCards));
    document.getElementById('selectVisible').addEventListener('click', () => {{
      cards.forEach(card => {{ if (!card.classList.contains('hidden')) selected.add(card.dataset.id); }});
      save();
      syncCards();
    }});
    document.getElementById('clearSelection').addEventListener('click', () => {{
      selected.clear();
      save();
      syncCards();
    }});
    document.getElementById('exportSelection').addEventListener('click', () => {{
      const approved = Array.from(selected).map(id => byId.get(id)).filter(Boolean);
      const json = JSON.stringify({{ generatedAt: new Date().toISOString(), approvedCount: approved.length, approvedCandidates: approved }}, null, 2);
      exportBox.value = json;
      exportPanel.classList.add('open');
      exportBox.focus();
      const blob = new Blob([json], {{ type: 'application/json' }});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'scorsatto-candidatos-aprovados-{Path(output_html).stem}.json';
      link.click();
      URL.revokeObjectURL(link.href);
    }});
    syncCards();
  </script>
</body>
</html>"""
    output_html.write_text(html, encoding="utf-8")


def candidate_score(item):
    text = f"{item.get('title','')} {item.get('url','')}".lower()
    score = 0
    for token in ("pima jersey", "supima", "algodao egipcio", "gola polo premium", "camisa social", "linho", "sueter", "jaqueta", "moletom"):
        if token in text:
            score += 10
    for token in ("preto", "branco", "off white", "azul marinho", "bege", "cinza", "marrom"):
        if token in text:
            score += 4
    for token in ("xe", "rl", "hb", "arm", "lct", "ck"):
        if f"-{token}" in text or f" {token} " in text:
            score += 3
    if item.get("brandLabel"):
        score += 4
    if item.get("collection"):
        score += 4
    score += min(len(item.get("sizes") or []), 5)
    if any(token in text for token in ("xadrez", "colors", "cafe", "gelo", "copia")):
        score -= 4
    return score


def write_priority_preview(candidates, output_html, categories=None, limit=36):
    priority = sorted(candidates, key=candidate_score, reverse=True)[:limit]
    write_preview(priority, output_html, categories=categories, title="Varredura fornecedor - prioridade para aprovacao")
    return priority


def main():
    products, _, _ = parse_products_from_index()
    site_categories, site_brands = parse_site_taxonomy()
    existing_urls = existing_supplier_urls(products)
    existing_ids = existing_supplier_ids(products)
    categories = discover_relevant_category_urls(site_categories)
    all_items = []
    errors = []
    for category in categories:
        try:
            all_items.extend(scan_category(category))
        except Exception as exc:
            errors.append({"category": category, "error": str(exc)})
    candidates = []
    seen = set()
    for item in all_items:
        if item["url"] in existing_urls or item["supplierProductId"] in existing_ids:
            continue
        if item["url"] in seen:
            continue
        enriched = enrich_supplier_item(item, site_categories, site_brands)
        if is_scorsatto_candidate(enriched, site_categories, site_brands):
            candidates.append(enriched)
            seen.add(item["url"])
    candidates.sort(key=lambda item: (item.get("collection", ""), item.get("brandLabel", ""), item.get("title", ""), item.get("supplierProductId", "")))
    day = today_slug()
    data_dir = ROOT / "data" / "fornecedor-varreduras"
    preview_dir = ROOT / "previews" / "fornecedor-varreduras"
    data_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / f"varredura-fornecedor-{day}.json"
    html_path = preview_dir / f"aprovacao-fornecedor-{day}.html"
    priority_html_path = preview_dir / f"aprovacao-fornecedor-prioridade-{day}.html"
    priority = write_priority_preview(candidates, priority_html_path, site_categories)
    payload = {
        "generatedAt": now_iso(),
        "categoryCount": len(categories),
        "siteCategories": site_categories,
        "siteBrands": site_brands,
        "scrapedItems": len(all_items),
        "candidateCount": len(candidates),
        "priorityCount": len(priority),
        "errors": errors,
        "priorityCandidates": priority,
        "candidates": candidates,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_preview(candidates, html_path, categories=site_categories)
    print(json.dumps({"candidates": len(candidates), "priority": len(priority), "json": str(json_path), "preview": str(html_path), "priorityPreview": str(priority_html_path), "errors": len(errors)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
