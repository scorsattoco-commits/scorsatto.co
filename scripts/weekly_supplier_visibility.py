"""Track confirmed supplier outages separately from products and physical stock."""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from supplier_common import ROOT, parse_products_from_index
from update_supplier_sizes import observe_supplier


PREFIX = "window.scorsattoSupplierUnavailable = "
VISIBILITY_PATH = ROOT / "supplier-visibility.js"


def supplier_url(value):
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme == "https"
        and parsed.netloc in {"catalogopoa.com.br", "www.catalogopoa.com.br"}
        and parsed.path not in {"", "/"}
    ):
        return value.rstrip("/")
    return ""


def public_manual_products():
    config = (ROOT / "supabase/config.js").read_text(encoding="utf-8")
    origin = re.search(r'SCORSATTO_SUPABASE_URL\s*=\s*["\'](https://[a-z0-9]+\.supabase\.co)["\']', config)
    key = re.search(r'SCORSATTO_SUPABASE_ANON_KEY\s*=\s*["\']([^"\']+)["\']', config)
    if not origin or not key:
        raise RuntimeError("Configuração pública do catálogo indisponível")
    endpoint = origin[1] + "/rest/v1/product_overrides?select=slug,data->_manualProduct&data->>_manualProduct=not.is.null&order=slug"
    products = []
    page_size = 200
    for offset in range(0, 30000, page_size):
        request = Request(
            endpoint + f"&offset={offset}&limit={page_size}",
            headers={"apikey": key[1], "Authorization": "Bearer " + key[1]},
        )
        with urlopen(request, timeout=25) as response:
            rows = json.load(response)
        if not isinstance(rows, list):
            raise RuntimeError("Resposta inesperada do catálogo complementar")
        products.extend(row["_manualProduct"] for row in rows if isinstance(row.get("_manualProduct"), dict))
        if len(rows) < page_size:
            return products
    raise RuntimeError("A consulta do catálogo complementar não atingiu a última página")


def verify(url):
    try:
        first = observe_supplier(url)
        if first["state"] not in {"available", "sold_out", "removed"}:
            return url, None, "Sem confirmação de disponibilidade"
        second = observe_supplier(url)
        if second["state"] != first["state"] or set(second["sizes"]) != set(first["sizes"]):
            return url, None, "As duas leituras divergiram"
        if first["state"] == "available" and not first["sizes"]:
            return url, None, "Disponibilidade sem grade confirmada"
        return url, first["state"], None
    except Exception as exc:
        return url, None, str(exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    products, _, _ = parse_products_from_index()
    products.extend(public_manual_products())
    urls = sorted({url for product in products if (url := supplier_url(product.get("supplierUrl")))})
    if not urls:
        raise RuntimeError("Nenhuma URL válida encontrada para conferência")
    old_data = VISIBILITY_PATH.read_text(encoding="utf-8").strip()
    if not old_data.startswith(PREFIX):
        raise RuntimeError("Arquivo de visibilidade inválido")
    previous = set(json.loads(old_data[len(PREFIX):].removesuffix(";")))
    unavailable = set(previous)
    failures = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, args.workers))) as pool:
        for url, state, error in pool.map(verify, urls):
            if error:
                failures.append({"url": url, "reason": error})
            elif state in {"sold_out", "removed"}:
                unavailable.add(url)
            elif state == "available":
                unavailable.discard(url)
    report = {
        "checked": len(urls), "confirmedUnavailable": len(unavailable),
        "newUnavailable": sorted(unavailable - previous), "restocked": sorted(previous - unavailable),
        "failures": failures, "applied": args.apply and bool(len(urls) - len(failures)),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if len(failures) == len(urls):
        raise SystemExit("Nenhuma referência foi confirmada. Visibilidade preservada.")
    if report["applied"] and unavailable != previous:
        VISIBILITY_PATH.write_text(PREFIX + json.dumps(sorted(unavailable), ensure_ascii=True) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
