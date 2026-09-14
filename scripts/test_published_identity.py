import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "data" / "fornecedor-varreduras" / "fila-publicada-site.json"
CORRECTED_IDS = {"15837", "16076", "16077", "16630", "16631"}
POLO_SPORT_IDS = {"16611", "16607", "16609", "16608"}


def main():
    data = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    assert data["groupCount"] == 13
    assert data["productCount"] == 47

    groups = {group["name"]: group for group in data["groups"]}
    plain = groups["Ralph Lauren - Camiseta Supima"]
    sport = groups["Ralph Lauren - Camiseta Supima Polo Sport"]
    fine = groups["Tommy Hilfiger - Calça Sarja Esporte Fino"]

    assert {item["supplierProductId"] for item in plain["products"]} == {"15837"}
    assert {item["supplierProductId"] for item in sport["products"]} == POLO_SPORT_IDS
    assert fine["siteGroupAction"] == "new-product"
    assert fine["siteGroupId"] is None
    assert all(group["identityReviewed"] for group in data["groups"])

    products = [item for group in data["groups"] for item in group["products"]]
    assert len(products) == len({item["supplierProductId"] for item in products}) == 47
    for item in products:
        assert item["referencePhoto"], item["supplierProductId"]
        assert item["supplierUrl"], item["supplierProductId"]
        photo = ROOT / item["photo"]
        assert photo.exists(), photo
        if item["supplierProductId"] in CORRECTED_IDS:
            with Image.open(photo) as image:
                assert image.size == (1100, 1100), (item["supplierProductId"], image.size)
            assert item["imageCanvas"] == "1100x1100"

    print("OK: identidade, agrupamentos e padrão 1100x1100 validados para as correções.")


if __name__ == "__main__":
    main()
