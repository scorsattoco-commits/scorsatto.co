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


def parse_site_taxonomy(path=INDEX_PATH):
    html = path.read_text(encoding="utf-8")
    categories_match = re.search(r"const\s+CATEGORIES\s*=\s*(\[.*?\]);\s*const\s+BRANDS\s*=", html, re.S)
    brands_match = re.search(r"const\s+BRANDS\s*=\s*(\[.*?\]);", html, re.S)
    if not categories_match or not brands_match:
        raise RuntimeError("Nao encontrei CATEGORIES/BRANDS no index.html")
    categories = json.loads(categories_match.group(1))
    brands = json.loads(brands_match.group(1))
    return categories, brands


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


def category_terms_from_site(categories):
    terms = set()
    manual = {
        "camisetas": ("camisetas", "camiseta", "algodao-egipcio", "algodao-supima", "supima", "pima", "texturizada"),
        "manga-longa": ("manga-longa", "camiseta-manga-longa"),
        "gola-polo": ("gola-polo", "gola polo"),
        "camisa-social": ("camisa-social", "camisa social"),
        "calcas": ("calcas", "calca", "calca-moletom"),
        "sueteres": ("sueter", "sueteres"),
        "jaquetas": ("jaquetas", "jaqueta", "bobojaco", "bomber", "puffer", "corta-vento"),
        "casacos": ("casaco", "casacos", "casaco-de-moletom", "moletom"),
        "bermudas": ("bermudas", "bermuda"),
    }
    for category in categories:
        slug = category.get("slug") or ""
        collection = category.get("collection") or ""
        if collection:
            terms.add(collection.lower())
        if slug and slug not in ("todos", "disponiveis-agora"):
            terms.add(slug.lower())
        for value in manual.get(slug, ()):
            terms.add(value.lower())
        for spec in category.get("specs") or []:
            for term in spec.get("terms") or []:
                terms.add(str(term).lower().replace(" ", "-"))
    return terms


def discover_relevant_category_urls(categories=None):
    if categories is None:
        categories, _ = parse_site_taxonomy()
    xml = fetch_text("https://www.catalogopoa.com.br/sitemap_category.xml")
    urls = re.findall(r"<loc>(.*?)</loc>", xml)
    allow = category_terms_from_site(categories)
    deny = ("feminino", "promocao", "promo", "plus", "regata", "tactel", "overs", "tamanhos-especiais")
    selected = []
    for url in urls:
        low = url.lower()
        if any(token in low for token in allow) and not any(token in low for token in deny):
            selected.append(url)
    return selected


def brand_from_item(item, brands=None):
    if brands is None:
        _, brands = parse_site_taxonomy()
    text = f"{item.get('title','')} {item.get('url','')}".lower()
    for brand in brands:
        if brand.get("selectableOnly"):
            continue
        codes = [str(code).lower() for code in brand.get("codes") or []]
        terms = [str(term).lower() for term in brand.get("terms") or []]
        code_hit = any(re.search(rf"(^|[-_\s]){re.escape(code)}($|[-_\s0-9])", text) for code in codes if code)
        term_hit = any(term and term in text for term in terms)
        if code_hit or term_hit:
            return brand.get("label") or "Sem marca"
    return ""


def collection_from_item(item, categories=None):
    if categories is None:
        categories, _ = parse_site_taxonomy()
    text = f"{item.get('title','')} {item.get('url','')} {item.get('categoryUrl','')}".lower()
    checks = (
        ("gola-polo", ("gola-polo", "gola polo")),
        ("camisa-social", ("camisa-social", "camisa social")),
        ("manga-longa", ("manga-longa", "manga longa")),
        ("calcas", ("calcas", "calca", "calça")),
        ("bermudas", ("bermuda", "bermudas")),
        ("sueteres", ("sueter", "sueteres", "sweater")),
        ("jaquetas", ("jaqueta", "jaquetas", "bobojaco", "bomber", "puffer", "corta-vento", "corta vento")),
        ("casacos", ("casaco", "casacos", "moletom")),
        ("camisetas", ("camiseta", "camisetas", "supima", "pima", "algodao", "algodão")),
    )
    site_collections = {c.get("collection") for c in categories if c.get("collection")}
    for collection, tokens in checks:
        if collection in site_collections and any(token in text for token in tokens):
            return collection
    return ""


def enrich_supplier_item(item, categories=None, brands=None):
    enriched = dict(item)
    enriched["brandLabel"] = brand_from_item(enriched, brands)
    enriched["collection"] = collection_from_item(enriched, categories)
    return enriched


def is_scorsatto_candidate(item, categories=None, brands=None):
    categories = categories or parse_site_taxonomy()[0]
    brands = brands or parse_site_taxonomy()[1]
    item = enrich_supplier_item(item, categories, brands)
    text = f"{item.get('title','')} {item.get('url','')} {item.get('categoryUrl','')}".lower()
    allow_brand = bool(item.get("brandLabel"))
    allow_collection = bool(item.get("collection"))
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
    deny = any(token in text for token in ("feminino", "infantil", "regata", "oversized", "plus", "short doll", "tactel", "poliamida", "praia"))
    return allow_brand and allow_collection and allow_product and not deny and bool(item.get("sizes"))
