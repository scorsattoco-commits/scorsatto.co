import { readFile, writeFile } from "node:fs/promises";

const SITE_ORIGIN = "https://usescorsatto.com.br/";
const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const match = html.match(/const PRODUCTS = (\[.*?\]);/s);

if (!match) throw new Error("Lista PRODUCTS não encontrada em index.html.");

const products = JSON.parse(match[1]);
const seenRefs = new Set();
const catalog = products.map((product) => {
  const ref = String(product.supplierProductId || "").trim();
  if (!ref) throw new Error(`Produto sem Ref: ${product.name || product.id}`);
  const refKey = ref.toUpperCase();
  if (seenRefs.has(refKey)) throw new Error(`Ref duplicada no catálogo: ${ref}`);
  seenRefs.add(refKey);
  return {
    ref,
    name: product.name,
    imageUrl: new URL(product.images?.[0] || "", SITE_ORIGIN).href,
    productUrl: new URL(`/#produto-${product.slug}`, SITE_ORIGIN).href,
    category: product.collection || "",
    updatedAt: product.lastCheckedAt || null
  };
});

await writeFile(
  new URL("../catalogo.json", import.meta.url),
  JSON.stringify({ version: 1, generatedAt: new Date().toISOString(), products: catalog }, null, 2) + "\n",
  "utf8"
);

console.log(`Catálogo gerado com ${catalog.length} referências.`);
