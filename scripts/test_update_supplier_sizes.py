import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


sys.path.insert(0, str(Path(__file__).resolve().parent))

from supplier_common import parse_supplier_availability
from update_supplier_sizes import normalize_sizes, observe_supplier, stock_from_sizes


class UpdateSupplierSizesTest(unittest.TestCase):
    def test_stock_has_one_unit_for_each_available_size(self):
        self.assertEqual({"P": 1, "M": 1, "G": 1}, stock_from_sizes(["P", "M", "G"]))

    def test_empty_supplier_sizes_never_invent_stock(self):
        self.assertEqual({}, stock_from_sizes([]))

    def test_sizes_are_normalized_in_catalog_order(self):
        self.assertEqual(["P", "M", "GG", "38", "40"], normalize_sizes(["40", "GG", "P", "38", "M", "P"]))

    def test_explicit_sold_out_is_not_a_parser_failure(self):
        html = "<main>Lamentamos mas este produto está esgotado</main>"
        self.assertEqual({"state": "sold_out", "sizes": [], "evidence": "explicit-sold-out-message"}, parse_supplier_availability(html))

    def test_missing_sizes_without_evidence_fails_closed(self):
        result = parse_supplier_availability("<main>Produto temporariamente sem dados</main>")
        self.assertEqual("unknown", result["state"])

    def test_available_sizes_win_over_unavailable_words_elsewhere(self):
        html = '<li data-product-option-value-id="1"> M </li><footer>produto indisponível em outra cor</footer>'
        self.assertEqual({"state": "available", "sizes": ["M"], "evidence": "size-options"}, parse_supplier_availability(html))

    def test_http_404_is_a_confirmable_supplier_removal(self):
        error = HTTPError("https://fornecedor.example/removido", 404, "Not Found", None, None)
        with patch("update_supplier_sizes.fetch_text", side_effect=error):
            self.assertEqual({"state": "removed", "sizes": [], "evidence": "http-404"}, observe_supplier("https://fornecedor.example/removido"))


if __name__ == "__main__":
    unittest.main()
