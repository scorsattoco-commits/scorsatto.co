import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from supplier_common import (
    ROOT,
    fetch_text,
    now_iso,
    parse_products_from_index,
    parse_sizes_from_product_html,
    today_slug,
    write_products_to_index,
)


def stock_from_sizes(sizes):
    return {size: 1 for size in sizes}


def main():
    parser = argparse.ArgumentParser(description="Atualiza tamanhos do fornecedor no catalogo SCORSATTO.")
    parser.add_argument("--apply", action="store_true", help="Aplica no index.html. Sem este argumento, gera apenas relatorio.")
    parser.add_argument("--limit", type=int, default=0, help="Limita a quantidade de produtos conferidos.")
    parser.add_argument("--workers", type=int, default=8, help="Quantidade de consultas simultaneas.")
    args = parser.parse_args()
    products, html, span = parse_products_from_index()
    changes = []
    failures = []
    checked_at = today_slug()

    supplier_products = [product for product in products if "catalogopoa.com.br" in str(product.get("supplierUrl", ""))]
    if args.limit:
        supplier_products = supplier_products[: args.limit]
    product_by_id = {product.get("id"): product for product in supplier_products}

    def check_product(product):
        url = product.get("supplierUrl", "")
        try:
            page = fetch_text(url)
            sizes = parse_sizes_from_product_html(page)
            if not sizes:
                return {"type": "failure", "id": product.get("id"), "url": url, "reason": "sem tamanhos detectados"}
            old_sizes = product.get("sizes") or []
            if sizes != old_sizes:
                return {"type": "change", "id": product.get("id"), "name": product.get("name"), "url": url, "oldSizes": old_sizes, "newSizes": sizes}
            return {"type": "ok", "id": product.get("id"), "url": url, "sizes": sizes}
        except Exception as exc:
            return {"type": "failure", "id": product.get("id"), "url": url, "reason": str(exc)}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(check_product, product) for product in supplier_products]
        for future in as_completed(futures):
            result = future.result()
            if result["type"] == "failure":
                failures.append({"id": result.get("id"), "url": result.get("url"), "reason": result.get("reason")})
            elif result["type"] == "change":
                changes.append({"id": result.get("id"), "name": result.get("name"), "url": result.get("url"), "oldSizes": result.get("oldSizes"), "newSizes": result.get("newSizes")})
                if args.apply:
                    product = product_by_id.get(result.get("id"))
                    if product is not None:
                        product["sizes"] = result["newSizes"]
                        product["stock"] = stock_from_sizes(result["newSizes"])
                        product["lastCheckedAt"] = checked_at
    if args.apply and changes:
        write_products_to_index(products, html, span)
    out_dir = ROOT / "data" / "fornecedor-tamanhos"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"atualizacao-tamanhos-{today_slug()}.json"
    payload = {
        "generatedAt": now_iso(),
        "apply": args.apply,
        "checked": len(supplier_products),
        "changed": len(changes),
        "failures": failures,
        "changes": changes,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked": len(supplier_products), "changed": len(changes), "failures": len(failures), "applied": bool(args.apply and changes), "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
