import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError

from supplier_common import (
    ROOT,
    fetch_text,
    now_iso,
    parse_products_from_index,
    parse_supplier_availability,
    today_slug,
    write_products_to_index,
)


def stock_from_sizes(sizes):
    return {size: 1 for size in sizes}


SIZE_ORDER = {size: index for index, size in enumerate(("PP", "P", "M", "G", "GG", "XG", "XXG", "3G", "4G"))}


def normalize_sizes(sizes):
    unique = {str(size).strip().upper() for size in (sizes or []) if str(size).strip()}
    return sorted(unique, key=lambda size: (SIZE_ORDER.get(size, 100), int(size) if size.isdigit() else 999, size))


def observe_supplier(url):
    try:
        return parse_supplier_availability(fetch_text(url))
    except HTTPError as exc:
        if exc.code == 404:
            return {"state": "removed", "sizes": [], "evidence": "http-404"}
        raise


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

    supplier_products = [
        product
        for product in products
        if "catalogopoa.com.br" in str(product.get("supplierUrl", ""))
        and "estoque proprio" not in str(product.get("supplierName", "")).lower()
    ]
    if args.limit:
        supplier_products = supplier_products[: args.limit]
    product_by_id = {product.get("id"): product for product in supplier_products}

    def check_product(product):
        url = product.get("supplierUrl", "")
        try:
            first = observe_supplier(url)
            if first["state"] == "unknown":
                first = observe_supplier(url)
            if first["state"] == "unknown":
                return {"type": "failure", "failureType": "inconclusive", "id": product.get("id"), "url": url, "reason": "página sem tamanhos e sem mensagem explícita de esgotado"}

            old_sizes = normalize_sizes(product.get("sizes") or [])
            new_sizes = normalize_sizes(first.get("sizes") or [])
            if new_sizes != old_sizes:
                # Qualquer alteração precisa aparecer igual em duas leituras
                # independentes. Isso evita apagar ou inventar tamanho por uma
                # resposta parcial/transitória do fornecedor.
                second = observe_supplier(url)
                second_sizes = normalize_sizes(second.get("sizes") or [])
                if second["state"] != first["state"] or second_sizes != new_sizes:
                    return {"type": "failure", "failureType": "divergent", "id": product.get("id"), "url": url, "reason": "duas leituras do fornecedor apresentaram resultados diferentes"}
                return {
                    "type": "change",
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "url": url,
                    "oldSizes": old_sizes,
                    "newSizes": new_sizes,
                    "availabilityState": first["state"],
                    "evidence": first["evidence"],
                    "confirmedReads": 2,
                }
            return {"type": "ok", "id": product.get("id"), "url": url, "sizes": new_sizes, "availabilityState": first["state"]}
        except Exception as exc:
            return {"type": "failure", "failureType": "request-error", "id": product.get("id"), "url": url, "reason": str(exc)}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(check_product, product) for product in supplier_products]
        for future in as_completed(futures):
            result = future.result()
            if result["type"] == "failure":
                failures.append({"id": result.get("id"), "url": result.get("url"), "failureType": result.get("failureType"), "reason": result.get("reason")})
            elif result["type"] == "change":
                changes.append({"id": result.get("id"), "name": result.get("name"), "url": result.get("url"), "oldSizes": result.get("oldSizes"), "newSizes": result.get("newSizes"), "availabilityState": result.get("availabilityState"), "evidence": result.get("evidence"), "confirmedReads": result.get("confirmedReads")})
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
        "succeeded": len(supplier_products) - len(failures),
        "failureCount": len(failures),
        "failureRate": round((len(failures) / len(supplier_products)) * 100, 1) if supplier_products else 0,
        "health": "critical" if supplier_products and len(failures) / len(supplier_products) >= 0.2 else ("attention" if failures else "healthy"),
        "failures": failures,
        "changes": changes,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked": len(supplier_products), "changed": len(changes), "failures": len(failures), "applied": bool(args.apply and changes), "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
