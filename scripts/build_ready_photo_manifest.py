from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--day", required=True)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    site_root = ROOT / "generated" / "aprovadas" / "site"
    web_dir = site_root / args.day / "web"
    review_dir = ROOT / "generated" / "aprovadas" / "revisao" / args.day
    manifest_dir = ROOT / "data" / "fornecedor-varreduras"
    web_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    ready = {}
    missing = []
    review_rows = []
    for group in queue.get("groups", []):
        for product in group.get("products", []):
            product_id = str(product.get("supplierProductId") or "")
            candidates = list(site_root.rglob(f"scp-{product_id}-*.png"))
            candidates.sort(key=lambda path: (args.day in path.parts, path.stat().st_mtime), reverse=True)
            if not candidates:
                missing.append(product_id)
                continue
            source = candidates[0]
            image = Image.open(source).convert("RGB")
            image.thumbnail((1100, 1100), Image.Resampling.LANCZOS)
            target = web_dir / f"scp-{product_id}.webp"
            image.save(target, "WEBP", quality=88, method=6)
            relative = str(target.relative_to(ROOT)).replace("\\", "/")
            ready[product_id] = {
                "photo": relative,
                "source": str(source.relative_to(ROOT)).replace("\\", "/"),
                "status": "foto-pronta-revisao-humana",
            }
            review_rows.append((group.get("name", "Grupo"), product, target))

    cell_w, cell_h = 250, 310
    columns = 5
    rows = (len(review_rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h + 60), "#d8d1c6")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 18), f"SCORSATTO | FOTOS PRONTAS | {args.day} | {len(review_rows)} PECAS", fill="#171512", font=font)
    for index, (group_name, product, photo_path) in enumerate(review_rows):
        col, row = index % columns, index // columns
        x0, y0 = col * cell_w, row * cell_h + 60
        draw.rectangle((x0 + 5, y0 + 5, x0 + cell_w - 5, y0 + cell_h - 5), fill="#f3eee6")
        image = Image.open(photo_path).convert("RGB")
        image.thumbnail((220, 230), Image.Resampling.LANCZOS)
        sheet.paste(image, (x0 + (cell_w - image.width) // 2, y0 + 10))
        label = f"{product.get('supplierProductId')} | {product.get('detectedColor', '')}"
        draw.text((x0 + 12, y0 + 248), label[:38], fill="#171512", font=font)
        draw.text((x0 + 12, y0 + 266), str(group_name)[:36], fill="#5e574d", font=font)

    review_path = review_dir / "00-revisao-fotos-prontas-scorsatto.jpg"
    sheet.save(review_path, quality=90)
    payload = {
        "day": args.day,
        "generatedAt": queue.get("generatedAt"),
        "rule": "Foto pronta para revisao humana; nao publicar automaticamente no site.",
        "productCount": len(ready),
        "missing": missing,
        "photos": ready,
        "reviewSheet": str(review_path.relative_to(ROOT)).replace("\\", "/"),
    }
    dated = manifest_dir / f"fotos-prontas-site-{args.day}.json"
    stable = manifest_dir / "fotos-prontas-site.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    dated.write_text(content, encoding="utf-8")
    stable.write_text(content, encoding="utf-8")
    curated_groups = []
    for group in queue.get("groups", []):
        curated_products = []
        for product in group.get("products", []):
            product_id = str(product.get("supplierProductId") or "")
            photo = ready.get(product_id)
            if not photo:
                continue
            curated_products.append({
                "supplierProductId": product_id,
                "title": product.get("title"),
                "detectedColor": product.get("detectedColor"),
                "sizes": product.get("sizes") or [],
                "url": product.get("url"),
                "photo": photo["photo"],
                "status": photo["status"],
            })
        if curated_products:
            curated_groups.append({
                "id": group.get("id"),
                "name": group.get("name"),
                "brand": group.get("brand"),
                "collection": group.get("collection"),
                "count": len(curated_products),
                "products": curated_products,
            })

    curation_payload = {
        "day": args.day,
        "generatedAt": queue.get("generatedAt"),
        "rule": "Fotos prontas para revisao humana; nenhuma peca e publicada automaticamente.",
        "status": "aguardando-revisao-humana",
        "groupCount": len(curated_groups),
        "productCount": sum(len(group["products"]) for group in curated_groups),
        "groups": curated_groups,
    }
    curation_dated = manifest_dir / f"fila-curadoria-pronta-{args.day}.json"
    curation_stable = manifest_dir / "fila-curadoria-pronta.json"
    curation_content = json.dumps(curation_payload, ensure_ascii=False, indent=2)
    curation_dated.write_text(curation_content, encoding="utf-8")
    curation_stable.write_text(curation_content, encoding="utf-8")
    print(json.dumps({"products": len(ready), "groups": len(curated_groups), "missing": missing, "manifest": str(stable), "curation": str(curation_stable), "review": str(review_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
