import json
import re

from supplier_common import ROOT, now_iso, parse_products_from_index, today_slug


REPORT_DIR = ROOT / "data" / "automacoes"
PREVIEW_DIR = ROOT / "previews" / "automacoes"


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def product_name(product):
    name = clean(product.get("name"))
    color = clean(product.get("color"))
    return f"{name} - {color}" if color and color.lower() not in name.lower() else name


def product_brand(product):
    return clean(product.get("brand") or product.get("brandLabel") or product.get("brandName") or "Sem marca")


def product_status(product):
    return clean(product.get("status") or product.get("availability") or product.get("badge") or "")


def product_sizes(product):
    sizes = product.get("sizes") or product.get("availableSizes") or []
    if isinstance(sizes, dict):
        sizes = [key for key, value in sizes.items() if value]
    return [clean(size) for size in sizes if clean(size)]


def product_images(product):
    images = product.get("images") or []
    if product.get("image"):
        images = [product["image"], *images]
    return [clean(image) for image in images if clean(image)]


def stock_size_queue(products):
    rows = []
    for product in products:
        sizes = product_sizes(product)
        status = product_status(product).lower()
        supplier_url = clean(product.get("supplierUrl"))
        if "vendido" in status:
            continue
        reason = ""
        if not sizes:
            reason = "sem tamanhos cadastrados"
        elif "consulta" in status and supplier_url:
            reason = "confirmar fornecedor"
        elif supplier_url and not product.get("lastCheckedAt"):
            reason = "nunca conferido automaticamente"
        if reason:
            rows.append(
                {
                    "id": product.get("id") or product.get("slug"),
                    "name": product_name(product),
                    "brand": product_brand(product),
                    "sizes": sizes,
                    "status": product_status(product),
                    "supplierUrl": supplier_url,
                    "reason": reason,
                }
            )
    return rows


def photo_queue(products):
    rows = []
    for product in products:
        images = product_images(product)
        text = " ".join(images).lower()
        reason = ""
        if not images:
            reason = "sem foto"
        elif any(token in text for token in ["fornecedor", "whatsapp", "print", "screenshot"]):
            reason = "foto de fornecedor/print"
        elif not any(token in text for token in ["generated/", "estoque-scorsatto/"]):
            reason = "origem de foto fora do padrao"
        elif len(images) < 2:
            reason = "sem segunda foto/detalhe"
        if reason:
            rows.append(
                {
                    "id": product.get("id") or product.get("slug"),
                    "name": product_name(product),
                    "brand": product_brand(product),
                    "color": clean(product.get("color")),
                    "reason": reason,
                    "images": images[:3],
                    "rule": "gerar em preview e aprovar antes de publicar",
                }
            )
    return rows


def supplier_scan_queue(products):
    brands = sorted({product_brand(product) for product in products if product_brand(product) != "Sem marca"})
    categories = sorted({clean(product.get("collection") or product.get("category")) for product in products if clean(product.get("collection") or product.get("category"))})
    return {
        "brands": brands,
        "categories": categories,
        "rule": "varrer fornecedor por marca/categoria, agrupar por modelo e gerar preview para aprovacao",
    }


def latest_json(folder, pattern):
    paths = sorted(folder.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return None
    try:
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
        payload["_path"] = str(paths[0])
        return payload
    except Exception:
        return {"ok": False, "_path": str(paths[0]), "warnings": ["Arquivo encontrado, mas nao foi possivel ler o JSON."]}


def instagram_status():
    folder = REPORT_DIR / "instagram"
    sync = latest_json(folder, "instagram-sync-*.json")
    check = latest_json(folder, "instagram-backoffice-check-*.json")
    warnings = []
    for payload in [sync, check]:
        if not payload:
            continue
        warnings.extend(payload.get("warnings", []))
        for item in payload.get("checks", []):
            if not item.get("ok"):
                warnings.append(f"{item.get('name')}: {item.get('detail')}")
    return {
        "sync": sync,
        "check": check,
        "ok": bool(check and check.get("ok")),
        "found": int((sync or {}).get("found") or 0),
        "imported": int((sync or {}).get("imported") or 0),
        "sampleLeads": (check or {}).get("sampleLeads", []),
        "warnings": warnings[:8],
        "nextStep": (check or {}).get("nextStep") or "Configurar Meta/Supabase para puxar leads reais.",
    }


def html_table(headers, rows):
    if not rows:
        return "<p>Nenhum item encontrado.</p>"
    head = "".join(f"<th>{label}</th>" for label in headers.values())
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{clean(row.get(key, ''))}</td>" for key in headers.keys()) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_preview(payload):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = PREVIEW_DIR / f"painel-automatico-{today_slug()}.html"
    stock = payload["stockSizeQueue"]
    photos = payload["photoQueue"]
    instagram = payload["instagram"]
    instagram_rows = [
        {
            "name": lead.get("name") or "-",
            "handle": lead.get("handle") or "-",
            "source": lead.get("source") or "-",
            "score": lead.get("score") or 0,
        }
        for lead in instagram.get("sampleLeads", [])
    ]
    warning_rows = [{"warning": item} for item in instagram.get("warnings", [])]
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Painel automatico SCORSATTO - {today_slug()}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111; background: #f7f6f2; }}
    h1 {{ font-family: Georgia, serif; font-weight: 400; font-size: 48px; margin: 0 0 8px; }}
    section {{ background: #fff; border: 1px solid #ddd8cf; padding: 18px; margin: 18px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-top: 1px solid #ddd8cf; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #666; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .card {{ background: #fff; border: 1px solid #ddd8cf; padding: 16px; }}
    .card strong {{ display: block; font-size: 32px; }}
  </style>
</head>
<body>
  <h1>Painel automatico</h1>
  <p>Gerado em {payload["generatedAt"]}. Nada foi publicado no site.</p>
  <div class="cards">
    <div class="card"><strong>{payload["totalProducts"]}</strong><span>pecas no catalogo</span></div>
    <div class="card"><strong>{len(stock)}</strong><span>estoque/tamanhos para conferir</span></div>
    <div class="card"><strong>{len(photos)}</strong><span>fotos para preview</span></div>
    <div class="card"><strong>{instagram["imported"]}</strong><span>leads Instagram importados</span></div>
  </div>
  <section>
    <h2>Backoffice / Instagram real</h2>
    <p>Status: <strong>{'OK' if instagram["ok"] else 'PENDENTE'}</strong></p>
    <p>{instagram["nextStep"]}</p>
    {html_table({"name": "Nome", "handle": "@", "source": "Origem", "score": "Score"}, instagram_rows)}
    <h3>Pendencias</h3>
    {html_table({"warning": "Item"}, warning_rows)}
  </section>
  <section>
    <h2>Backoffice / Rotina diaria de tamanhos</h2>
    {html_table({"name": "Produto", "brand": "Marca", "sizes": "Tamanhos", "status": "Status", "reason": "Acao"}, stock)}
  </section>
  <section>
    <h2>Comercial / Pipeline de fotos</h2>
    {html_table({"name": "Produto", "brand": "Marca", "color": "Cor", "reason": "Motivo", "rule": "Regra"}, photos)}
  </section>
  <section>
    <h2>Comercial / Varredura de fornecedor</h2>
    <p>Marcas no site: {", ".join(payload["supplierScan"]["brands"])}</p>
    <p>Categorias no site: {", ".join(payload["supplierScan"]["categories"])}</p>
    <p>{payload["supplierScan"]["rule"]}</p>
  </section>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    return path


def main():
    products, _, _ = parse_products_from_index()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": now_iso(),
        "totalProducts": len(products),
        "stockSizeQueue": stock_size_queue(products),
        "photoQueue": photo_queue(products),
        "supplierScan": supplier_scan_queue(products),
        "instagram": instagram_status(),
        "publishRule": "nao publicar automaticamente; gerar preview e aguardar aprovacao",
    }
    report_path = REPORT_DIR / f"painel-automatico-{today_slug()}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    preview_path = write_preview(payload)
    print(json.dumps({"report": str(report_path), "preview": str(preview_path), "stock": len(payload["stockSizeQueue"]), "photos": len(payload["photoQueue"]), "instagram": payload["instagram"]["imported"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
