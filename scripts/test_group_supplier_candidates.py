import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from group_supplier_candidates import group_items


def candidate(ref, title, brand="Marca X", collection="camisetas", sizes=None):
    return {
        "supplierProductId": ref,
        "title": title,
        "brandLabel": brand,
        "collection": collection,
        "sizes": sizes or [],
        "url": f"https://fornecedor.example/{ref}",
    }


class GroupSupplierCandidatesTest(unittest.TestCase):
    def test_same_piece_different_colors_stays_in_one_group(self):
        items = [
            candidate("101", "Camiseta Pima Jersey XE - Preto", sizes=["P", "M"]),
            candidate("102", "Camiseta Pima Jersey XE - Bege", sizes=["G"]),
        ]

        groups, singles = group_items(items)

        self.assertEqual(1, len(groups))
        self.assertEqual([], singles)
        self.assertEqual({"P", "M", "G"}, set(groups[0]["sizes"]))
        self.assertEqual({"Preto", "Bege"}, set(groups[0]["colors"]))

    def test_truncated_supplier_codes_do_not_split_the_same_piece(self):
        items = [
            candidate("111", "Camiseta Cotton Egípcio XE Básica - Preto - cottx..."),
            candidate("112", "Camiseta Cotton Egípcio XE Básica - Branco - cottxe..."),
        ]

        groups, singles = group_items(items)

        self.assertEqual(1, len(groups))
        self.assertEqual(2, groups[0]["count"])
        self.assertEqual([], singles)

    def test_same_piece_without_visual_detail_is_grouped_for_review(self):
        items = [
            candidate("201", "Camiseta Classic XE - Preto"),
            candidate("202", "Camiseta Classic XE - Branco"),
        ]

        groups, singles = group_items(items)

        self.assertEqual(1, len(groups))
        self.assertEqual("revisar", groups[0]["status"])
        self.assertEqual([], singles)

    def test_different_models_never_mix(self):
        items = [
            candidate("301", "Camiseta Pima Jersey XE - Preto"),
            candidate("302", "Camiseta Pima Jersey XE Manga Longa - Preto"),
        ]

        groups, singles = group_items(items)

        self.assertEqual([], groups)
        self.assertEqual(2, len(singles))

    def test_different_brands_never_mix(self):
        items = [
            candidate("401", "Camiseta Pima Jersey XE - Preto", brand="Marca X"),
            candidate("402", "Camiseta Pima Jersey XE - Preto", brand="Marca Y"),
        ]

        groups, singles = group_items(items)

        self.assertEqual([], groups)
        self.assertEqual(2, len(singles))

    def test_duplicate_supplier_reference_is_not_repeated(self):
        items = [
            candidate("501", "Camiseta Pima Jersey XE - Preto", sizes=["P"]),
            candidate("501", "Camiseta Pima Jersey XE - Preto", sizes=["P"]),
            candidate("502", "Camiseta Pima Jersey XE - Bege", sizes=["M"]),
        ]

        groups, singles = group_items(items)

        self.assertEqual(1, len(groups))
        self.assertEqual(2, groups[0]["count"])
        self.assertEqual([], singles)

    def test_womenswear_never_enters_menswear_curadoria(self):
        items = [
            candidate("601", "Camiseta Jersey Feminina XE - Preto"),
            candidate("602", "Camiseta Jersey Feminina XE - Branco"),
        ]

        groups, singles = group_items(items)

        self.assertEqual([], groups)
        self.assertEqual([], singles)


if __name__ == "__main__":
    unittest.main()
