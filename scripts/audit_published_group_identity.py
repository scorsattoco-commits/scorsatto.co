import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "index.html").read_text(encoding="utf-8")


def read_array(name):
    marker = f"const {name} = "
    start = SOURCE.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(SOURCE[start:])[0]


products = read_array("PRODUCTS")
groups = read_array("PRODUCT_GROUPS")
by_slug = {product.get("slug"): product for product in products}
target_ids = [
    "aprovado-2026-07-29-lacoste-gola-polo-premium",
    "json-rl-supima",
    "aprovado-2026-09-11-tommy-hilfiger-calca-sarja",
    "aprovado-2026-07-12-ralph-lauren-calca-sarja",
    "json-mang-longa-tommy-1",
    "aprovado-2026-07-12-ralph-lauren-camisa-social-oxford",
]

for group_id in target_ids:
    group = next((item for item in groups if item.get("id") == group_id), None)
    print(f"\n### {group_id}")
    for slug in (group or {}).get("slugs", []):
        product = by_slug.get(slug, {})
        print(json.dumps({
            "ref": product.get("supplierProductId"),
            "name": product.get("name"),
            "image": (product.get("images") or [None])[0],
            "supplier": product.get("supplierUrl"),
            "notes": product.get("internalNotes"),
        }, ensure_ascii=False))
