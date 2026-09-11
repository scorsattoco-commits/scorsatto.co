from __future__ import annotations

import argparse
import json
import shutil
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in normalized).split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--asset-manifest", required=True, type=Path)
    parser.add_argument("--day", required=True)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8-sig"))
    assets = json.loads(args.asset_manifest.read_text(encoding="utf-8"))["assets"]
    by_url = {asset["url"]: Path(asset["path"]) for asset in assets if asset.get("kind") == "image"}

    queue_dir = ROOT / "generated" / "aprovadas" / "fila"
    refs_dir = ROOT / "generated" / "aprovadas" / "referencias" / args.day
    sheets_dir = ROOT / "generated" / "aprovadas" / "contatos" / args.day
    queue_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    loader = queue_dir / f"carregador-referencias-{args.day}.html"
    loader_images = []
    for group in queue.get("approvedGroups", []):
        for product in group.get("products", []):
            loader_images.append(
                f'<figure><img src="{product.get("image", "")}" alt="{product.get("supplierProductId", "")}"><figcaption>{product.get("supplierProductId", "")} · {product.get("detectedColor", "")}</figcaption></figure>'
            )
    loader.write_text(
        '<!doctype html><meta charset="utf-8"><title>Referências aprovadas</title>'
        '<style>body{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;background:#eee9e0}'
        'figure{margin:0;background:white;padding:8px}img{width:100%;aspect-ratio:1;object-fit:contain}'
        'figcaption{font:12px Arial}</style>' + ''.join(loader_images),
        encoding="utf-8",
    )

    prepared = []
    missing = []
    for group_index, group in enumerate(queue.get("approvedGroups", []), 1):
        group_slug = slug(group["name"])
        group_rows = []
        for product in group.get("products", []):
            product_id = str(product["supplierProductId"])
            source = by_url.get(product.get("image"))
            if not source or not source.exists():
                missing.append({"id": product_id, "url": product.get("image")})
                continue
            suffix = source.suffix.lower() or ".jpg"
            target = refs_dir / f"scp-{product_id}-{slug(product.get('detectedColor') or 'cor')}{suffix}"
            shutil.copy2(source, target)
            row = {**product, "referencePath": str(target.relative_to(ROOT)).replace("\\", "/")}
            group_rows.append(row)

        if group_rows:
            cell = 320
            columns = min(3, len(group_rows))
            rows = (len(group_rows) + columns - 1) // columns
            sheet = Image.new("RGB", (columns * cell, rows * (cell + 48)), "#f1ece4")
            draw = ImageDraw.Draw(sheet)
            font = ImageFont.load_default()
            for index, product in enumerate(group_rows):
                col, row_index = index % columns, index // columns
                source_path = ROOT / product["referencePath"]
                image = Image.open(source_path).convert("RGB")
                image.thumbnail((cell - 30, cell - 30), Image.Resampling.LANCZOS)
                x = col * cell + (cell - image.width) // 2
                y = row_index * (cell + 48) + (cell - image.height) // 2
                sheet.paste(image, (x, y))
                label = f"{product['supplierProductId']} · {product.get('detectedColor') or 'cor'}"
                draw.text((col * cell + 12, row_index * (cell + 48) + cell + 12), label, fill="#171512", font=font)
            sheet_path = sheets_dir / f"{group_index:02d}-{group_slug}.jpg"
            sheet.save(sheet_path, quality=94)
        else:
            sheet_path = None

        prepared.append({
            "id": group["id"],
            "name": group["name"],
            "brand": group["brand"],
            "collection": group["collection"],
            "products": group_rows,
            "contactSheet": str(sheet_path.relative_to(ROOT)).replace("\\", "/") if sheet_path else None,
        })

    payload = {
        "generatedAt": queue.get("generatedAt"),
        "day": args.day,
        "groupCount": len(prepared),
        "productCount": sum(len(group["products"]) for group in prepared),
        "missing": missing,
        "groups": prepared,
    }
    output = queue_dir / f"fila-fotos-site-scorsatto-{args.day}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    contact_paths = [ROOT / group["contactSheet"] for group in prepared if group.get("contactSheet")]
    thumb_width = 720
    thumbs = []
    for contact_path in contact_paths:
        contact = Image.open(contact_path).convert("RGB")
        contact.thumbnail((thumb_width, 650), Image.Resampling.LANCZOS)
        thumbs.append(contact)
    master_height = sum(image.height + 24 for image in thumbs) + 24
    master = Image.new("RGB", (thumb_width + 48, master_height), "#dcd5ca")
    y = 24
    for image in thumbs:
        master.paste(image, ((master.width - image.width) // 2, y))
        y += image.height + 24
    master_path = sheets_dir / "00-todas-as-pecas-aprovadas.jpg"
    master.save(master_path, quality=92)
    print(json.dumps({"output": str(output), "loader": str(loader), "masterContactSheet": str(master_path), "groups": len(prepared), "products": payload["productCount"], "missing": len(missing)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
