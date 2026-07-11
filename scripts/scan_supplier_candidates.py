import json
import math
from pathlib import Path

from supplier_common import (
    ROOT,
    clean_text,
    discover_relevant_category_urls,
    existing_supplier_ids,
    existing_supplier_urls,
    fetch_text,
    is_scorsatto_candidate,
    parse_listing_products,
    parse_products_from_index,
    today_slug,
    now_iso,
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


def write_preview(candidates, output_html):
    cards = []
    for item in candidates:
        sizes = ", ".join(item.get("sizes") or [])
        cards.append(
            f"""
            <article class="card">
              <img src="{item.get('image','')}" alt="">
              <div class="body">
                <strong>{clean_text(item.get('title',''))}</strong>
                <span>Ref. {item.get('supplierProductId','')} · tamanhos: {sizes}</span>
                <span>Atacado: R$ {item.get('wholesalePrice') or '-'} · Varejo: R$ {item.get('retailPrice') or '-'}</span>
                <a href="{item.get('url','')}" target="_blank" rel="noreferrer">Abrir fornecedor</a>
                <div class="actions"><button>Aprovar</button><button>Reprovar</button><button>Ver foto</button></div>
              </div>
            </article>
            """
        )
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SCORSATTO - Varredura fornecedor</title>
  <style>
    body {{ margin:0; background:#f7f5ef; color:#181816; font-family:Inter,Arial,sans-serif; }}
    header {{ padding:28px 32px; background:#fff; border-bottom:1px solid #ddd8ce; position:sticky; top:0; z-index:2; }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    p {{ margin:0; color:#666; }}
    main {{ padding:24px; display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px; }}
    .card {{ background:#fff; border:1px solid #ded8ce; border-radius:8px; overflow:hidden; display:grid; }}
    img {{ width:100%; aspect-ratio:1/1; object-fit:contain; background:#f8f6f0; }}
    .body {{ padding:14px; display:grid; gap:8px; }}
    strong {{ font-size:14px; line-height:1.35; }}
    span, a {{ font-size:12px; color:#5f5b53; }}
    a {{ color:#111; font-weight:700; }}
    .actions {{ display:flex; gap:8px; margin-top:6px; }}
    button {{ border:1px solid #111; border-radius:6px; background:#111; color:#fff; min-height:34px; padding:0 10px; font-weight:700; }}
    button + button {{ background:#fff; color:#111; }}
  </style>
</head>
<body>
  <header>
    <h1>Varredura fornecedor - candidatos para aprovação</h1>
    <p>{len(candidates)} peças novas encontradas. Nada foi inserido no site.</p>
  </header>
  <main>{''.join(cards) if cards else '<p>Nenhuma peça nova encontrada nesta varredura.</p>'}</main>
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
    for token in ("xe", "rl", "hb", "arm", "lct"):
        if f"-{token}" in text or f" {token} " in text:
            score += 3
    score += min(len(item.get("sizes") or []), 5)
    if any(token in text for token in ("xadrez", "colors", "cafe", "gelo", "copia")):
        score -= 4
    return score


def write_priority_preview(candidates, output_html, limit=36):
    priority = sorted(candidates, key=candidate_score, reverse=True)[:limit]
    write_preview(priority, output_html)
    return priority


def main():
    products, _, _ = parse_products_from_index()
    existing_urls = existing_supplier_urls(products)
    existing_ids = existing_supplier_ids(products)
    categories = discover_relevant_category_urls()
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
        if is_scorsatto_candidate(item):
            candidates.append(item)
            seen.add(item["url"])
    candidates.sort(key=lambda item: (item.get("title", ""), item.get("supplierProductId", "")))
    day = today_slug()
    data_dir = ROOT / "data" / "fornecedor-varreduras"
    preview_dir = ROOT / "previews" / "fornecedor-varreduras"
    data_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / f"varredura-fornecedor-{day}.json"
    html_path = preview_dir / f"aprovacao-fornecedor-{day}.html"
    priority_html_path = preview_dir / f"aprovacao-fornecedor-prioridade-{day}.html"
    priority = write_priority_preview(candidates, priority_html_path)
    payload = {
        "generatedAt": now_iso(),
        "categoryCount": len(categories),
        "scrapedItems": len(all_items),
        "candidateCount": len(candidates),
        "priorityCount": len(priority),
        "errors": errors,
        "priorityCandidates": priority,
        "candidates": candidates,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_preview(candidates, html_path)
    print(json.dumps({"candidates": len(candidates), "priority": len(priority), "json": str(json_path), "preview": str(html_path), "priorityPreview": str(priority_html_path), "errors": len(errors)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
