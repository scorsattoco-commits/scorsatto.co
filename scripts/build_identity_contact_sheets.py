import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "generated" / "aprovadas" / "fila" / "fila-fotos-site-scorsatto-2026-09-10.json"
PHOTOS = ROOT / "data" / "fornecedor-varreduras" / "fotos-prontas-site.json"
OUTPUT = ROOT / "previews" / "auditoria-identidade-2026-09-11"
OUTPUT.mkdir(parents=True, exist_ok=True)

queue = json.loads(QUEUE.read_text(encoding="utf-8"))
photos = json.loads(PHOTOS.read_text(encoding="utf-8"))["photos"]
font = ImageFont.load_default()


def fit_image(image_path, size=(360, 360)):
    image = Image.open(image_path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#f4f0e8")
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


for group_index, group in enumerate(queue["groups"], 1):
    rows = []
    for product in group["products"]:
        product_id = str(product["supplierProductId"])
        reference = ROOT / product["referencePath"]
        standard = ROOT / photos[product_id]["photo"]
        label = f'{product_id} | {product.get("detectedColor", "")} | {product.get("title", "")}'
        row = Image.new("RGB", (760, 420), "white")
        row.paste(fit_image(reference), (10, 45))
        row.paste(fit_image(standard), (390, 45))
        draw = ImageDraw.Draw(row)
        draw.text((10, 8), "REFERENCIA REAL", fill="#111", font=font)
        draw.text((390, 8), "FOTO SCORSATTO", fill="#111", font=font)
        draw.text((10, 28), textwrap.shorten(label, width=105), fill="#333", font=font)
        rows.append(row)
    sheet = Image.new("RGB", (760, 55 + 420 * len(rows)), "#e9e3d8")
    ImageDraw.Draw(sheet).text((14, 18), group["name"], fill="#111", font=font)
    for row_index, row in enumerate(rows):
        sheet.paste(row, (0, 55 + row_index * 420))
    safe_name = "-".join(group["name"].lower().replace("ç", "c").replace("ã", "a").split())
    sheet.save(OUTPUT / f"{group_index:02d}-{safe_name}.jpg", quality=90)

print(OUTPUT)
