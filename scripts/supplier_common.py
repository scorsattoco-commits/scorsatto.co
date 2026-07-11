import datetime as _dt
import html as _html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
USER_AGENT = "Mozilla/5.0 (SCORSATTO supplier audit)"


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_slug():
    return _dt.datetime.now().strftime("%Y-%m-%d")


def fetch_text(url, timeout=25, retries=2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", "ignore")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.2 + attempt)
    raise last_error


def clean_text(value):
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or ""))).strip()


def parse_products_from_index(path=INDEX_PATH):
    html = path.read_text(encoding="utf-8")
    match = re.search(r"const\s+PRODUCTS\s*=\s*(\[.*?\]);\s*const\s+CATEGORIES\s*=", html, re.S)
    if not match:
        raise RuntimeError("Nao encontrei const PRODUCTS no index.html")
    return json.loads(match.group(1)), html, match.span(1)


def write_products_to_index(products, html, span, path=INDEX_PATH):
    payload = json.dumps(products, ensure_ascii=False, separators=(",", ":"))
    path.write_text(html[: span[0]] + payload + html[span[1] :], encoding="utf-8")


def normalize_url(url):
    return (url or "").split("#", 1)[0].rstrip("/")


def existing_supplier_urls(products):
    return {normalize_url(p.get("supplierUrl")) for p in products if "catalogopoa.com.br" in str(p.get("supplierUrl", ""))}


def existing_supplier_ids(products):
    ids = set()
    for product in products:
        if product.get("supplierProductId"):
            ids.add(str(product["supplierProductId"]))
        if product.get("id", "").startswith("scp-"):
            ids.add(product["id"].replace("scp-", ""))
    return ids


def parse_sizes_from_product_html(html):
    sizes = []
    for match in re.finditer(r"<li\b([^>]*)>(.*?)</li>", html, re.S | re.I):
        attrs = match.group(1)
        if "data-product-option-value-id" not in attrs:
            continue
        if re.search(r"\b(disabled|unavailable|out-stock|no-stock)\b", attrs, re.I):
            continue
        size = clean_text(match.group(2))
        if size and size not in sizes:
            sizes.append(size)
    if sizes:
        return sizes
    for match in re.finditer(r"<span\b[^>]*size-name-cart[^>]*>(.*?)</span>", html, re.S | re.I):
        size = clean_text(match.group(1))
        if size and size not in sizes:
            sizes.append(size)
    return sizes


def parse_listing_products(html, base_url):
    items = []
    blocks = re.split(r'<div class="product-item\b', html, flags=re.I)
    for block in blocks[1:]:
        id_match = re.search(r'id="product_thumb_(\d+)"', block)
        link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]+title="([^"]+)"', block, re.S | re.I)
        if not id_match or not link_match:
            continue
        product_id = id_match.group(1)
        url = urljoin(base_url, _html.unescape(link_match.group(1)))
        title = clean_text(link_match.group(2))
        img_match = re.search(r'<img[^>]+(?:data-src|src)="([^"]+)"', block, re.S | re.I)
        wholesale = re.search(r"Preço\s+no\s+Atacado:\s*R\$\s*([0-9.,]+)", clean_text(block), re.I)
        retail = re.search(r"R\$\s*([0-9.,]+)", clean_text(block), re.I)
        sizes = []
        for size_match in re.finditer(r"<span\b[^>]*size-name-cart[^>]*>(.*?)</span>", block, re.S | re.I):
            size = clean_text(size_match.group(1))
            if size and size not in sizes:
                sizes.append(size)
        items.append(
            {
                "supplierProductId": product_id,
                "title": title,
                "url": normalize_url(url),
                "image": _html.unescape(img_match.group(1)) if img_match else "",
                "sizes": sizes,
                "retailPrice": retail.group(1) if retail else "",
                "wholesalePrice": wholesale.group(1) if wholesale else "",
            }
        )
    return items


def discover_relevant_category_urls():
    xml = fetch_text("https://www.catalogopoa.com.br/sitemap_category.xml")
    urls = re.findall(r"<loc>(.*?)</loc>", xml)
    allow = (
        "bermudas",
        "calcas",
        "camisa-social",
        "camisetas/algodao-egipcio",
        "camisetas/algodao-supima",
        "camisetas/manga-longa",
        "camisetas/pima",
        "camisetas/texturizada",
        "gola-polo/premium",
        "inverno/calca-moletom",
        "inverno/camiseta-manga-longa",
        "inverno/casaco-de-moletom",
        "inverno/jaquetas-bobojaco",
        "inverno/sueter",
    )
    deny = ("feminino", "promocao", "promo", "plus", "regata", "tactel", "overs", "tamanhos-especiais")
    selected = []
    for url in urls:
        low = url.lower()
        if any(token in low for token in allow) and not any(token in low for token in deny):
            selected.append(url)
    return selected


def is_scorsatto_candidate(item):
    text = f"{item.get('title','')} {item.get('url','')}".lower()
    allow_brand = any(token in text for token in (" xe", "-xe", " th", "-th", " rl", "-rl", " hb", "-hb", " lct", "-lct", " arm", "-arm"))
    allow_product = any(
        token in text
        for token in (
            "camiseta",
            "gola-polo",
            "gola polo",
            "camisa-social",
            "camisa social",
            "calca",
            "bermuda",
            "jaqueta",
            "moletom",
            "sueter",
            "malha",
        )
    )
    deny = any(token in text for token in ("feminino", "infantil", "regata", "oversized", "plus", "short doll"))
    return allow_brand and allow_product and not deny and bool(item.get("sizes"))
