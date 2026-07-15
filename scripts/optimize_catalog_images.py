import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps

from supplier_common import ROOT, parse_products_from_index, today_slug, write_products_to_index


OUT_DIR = ROOT / "generated" / "optimized" / "site"
REPORT_DIR = ROOT / "data" / "performance"


def optimized_name(src):
    path = Path(src)
    digest = hashlib.sha1(src.encode("utf-8")).hexdigest()[:10]
    return f"{path.stem}-{digest}.webp"


def optimize_image(src, max_width=900, quality=82):
    source = ROOT / src
    if not source.exists():
        return src, None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / optimized_name(src)
    if out_path.exists() and out_path.stat().st_mtime >= source.stat().st_mtime:
        return str(out_path.relative_to(ROOT)).replace("\\", "/"), {
            "source": src,
            "optimized": str(out_path.relative_to(ROOT)).replace("\\", "/"),
            "oldBytes": source.stat().st_size,
            "newBytes": out_path.stat().st_size,
            "cached": True,
        }
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize((max_width, max(1, int(image.height * ratio))), Image.Resampling.LANCZOS)
        image.save(out_path, "WEBP", quality=quality, method=6)
    return str(out_path.relative_to(ROOT)).replace("\\", "/"), {
        "source": src,
        "optimized": str(out_path.relative_to(ROOT)).replace("\\", "/"),
        "oldBytes": source.stat().st_size,
        "newBytes": out_path.stat().st_size,
        "cached": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Gera imagens WebP otimizadas para o catalogo SCORSATTO.")
    parser.add_argument("--apply", action="store_true", help="Atualiza index.html para usar as imagens otimizadas.")
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--max-width", type=int, default=900)
    args = parser.parse_args()

    products, html, span = parse_products_from_index()
    report = []
    changed = 0
    for product in products:
        images = []
        for src in product.get("images") or []:
            if src.lower().endswith(".webp") and src.startswith("generated/optimized/"):
                images.append(src)
                continue
            optimized, row = optimize_image(src, max_width=args.max_width, quality=args.quality)
            images.append(optimized)
            if row:
                report.append({**row, "product": product.get("name"), "id": product.get("id") or product.get("slug")})
                if optimized != src:
                    changed += 1
        if args.apply:
            product["images"] = images

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"otimizacao-imagens-{today_slug()}.json"
    old_total = sum(item["oldBytes"] for item in report)
    new_total = sum(item["newBytes"] for item in report)
    payload = {
        "apply": args.apply,
        "images": len(report),
        "changed": changed,
        "oldMB": round(old_total / 1024 / 1024, 2),
        "newMB": round(new_total / 1024 / 1024, 2),
        "savedMB": round((old_total - new_total) / 1024 / 1024, 2),
        "items": report,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.apply and changed:
        write_products_to_index(products, html, span)
    print(json.dumps({k: payload[k] for k in ("apply", "images", "changed", "oldMB", "newMB", "savedMB")} | {"report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
