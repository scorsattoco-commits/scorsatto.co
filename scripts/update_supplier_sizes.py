import argparse
import json

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
    args = parser.parse_args()
    products, html, span = parse_products_from_index()
    changes = []
    failures = []
    checked = 0
    checked_at = today_slug()
    for product in products:
        url = product.get("supplierUrl", "")
        if "catalogopoa.com.br" not in url:
            continue
        checked += 1
        try:
            page = fetch_text(url)
            sizes = parse_sizes_from_product_html(page)
            if not sizes:
                failures.append({"id": product.get("id"), "url": url, "reason": "sem tamanhos detectados"})
                continue
            old_sizes = product.get("sizes") or []
            if sizes != old_sizes:
                changes.append({"id": product.get("id"), "name": product.get("name"), "url": url, "oldSizes": old_sizes, "newSizes": sizes})
                if args.apply:
                    product["sizes"] = sizes
                    product["stock"] = stock_from_sizes(sizes)
                    product["lastCheckedAt"] = checked_at
        except Exception as exc:
            failures.append({"id": product.get("id"), "url": url, "reason": str(exc)})
    if args.apply and changes:
        write_products_to_index(products, html, span)
    out_dir = ROOT / "data" / "fornecedor-tamanhos"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"atualizacao-tamanhos-{today_slug()}.json"
    payload = {
        "generatedAt": now_iso(),
        "apply": args.apply,
        "checked": checked,
        "changed": len(changes),
        "failures": failures,
        "changes": changes,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checked": checked, "changed": len(changes), "failures": len(failures), "applied": bool(args.apply and changes), "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
