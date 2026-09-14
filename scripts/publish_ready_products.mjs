import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const INDEX = path.join(ROOT, 'index.html');
const QUEUE = path.join(ROOT, 'generated', 'aprovadas', 'fila', 'fila-fotos-site-scorsatto-2026-09-10.json');
const PHOTOS = path.join(ROOT, 'data', 'fornecedor-varreduras', 'fotos-prontas-site.json');
const PUBLISHED = path.join(ROOT, 'data', 'fornecedor-varreduras', 'fila-publicada-site.json');
const PUBLISHED_DATED = path.join(ROOT, 'data', 'fornecedor-varreduras', 'fila-publicada-site-2026-09-11.json');

const PRICES = new Map([
  ['Lacoste - Gola Polo Premium', 129.90],
  ['Lacoste - Camiseta Pima Jersey', 159.90],
  ['Ralph Lauren - Camiseta Supima', 129.90],
  ['Ralph Lauren - Camiseta Supima Polo Sport', 129.90],
  ['Tommy Hilfiger - Calça Sarja', 199.90],
  ['Tommy Hilfiger - Calça Sarja Esporte Fino', 199.90],
  ['Ralph Lauren - Calça Sarja', 199.90],
  ['Ralph Lauren - Camiseta Pima Jersey', 159.90],
  ['Lacoste - Moletom C Capuz Premium Live', 199.90],
  ['Tommy Hilfiger - Jaqueta Texturizada', 289.90],
  ['Tommy Hilfiger - Camiseta Manga Longa', 159.90],
  ['Tommy Hilfiger - Camisa Social Xadrez', 199.90],
  ['Ralph Lauren - Camisa Social Oxford', 199.90],
]);

const TARGETS = new Map([
  ['Lacoste - Gola Polo Premium', { id: 'aprovado-2026-07-29-lacoste-gola-polo-premium', action: 'merged-existing' }],
  ['Lacoste - Camiseta Pima Jersey', { id: 'aprovado-2026-09-11-lacoste-camiseta-pima-jersey', action: 'new-group' }],
  ['Ralph Lauren - Camiseta Supima', { id: 'json-rl-supima', action: 'merged-existing' }],
  ['Ralph Lauren - Camiseta Supima Polo Sport', { id: 'aprovado-2026-09-11-ralph-lauren-supima-polo-sport', action: 'new-group' }],
  ['Tommy Hilfiger - Calça Sarja', { id: 'aprovado-2026-09-11-tommy-hilfiger-calca-sarja', action: 'merged-existing', seed: ['calca-sarja-azul-marinho-15290', 'calca-sarja-preto-15287'] }],
  ['Tommy Hilfiger - Calça Sarja Esporte Fino', { action: 'new-product', standalone: true }],
  ['Ralph Lauren - Calça Sarja', { id: 'aprovado-2026-07-12-ralph-lauren-calca-sarja', action: 'merged-existing' }],
  ['Ralph Lauren - Camiseta Pima Jersey', { id: 'aprovado-2026-09-11-ralph-lauren-camiseta-pima-jersey', action: 'new-group' }],
  ['Lacoste - Moletom C Capuz Premium Live', { id: 'aprovado-2026-09-11-lacoste-moletom-capuz-premium-live', action: 'new-group' }],
  ['Tommy Hilfiger - Jaqueta Texturizada', { id: 'aprovado-2026-09-11-tommy-hilfiger-jaqueta-texturizada', action: 'new-group' }],
  ['Tommy Hilfiger - Camiseta Manga Longa', { id: 'json-mang-longa-tommy-1', action: 'merged-existing' }],
  ['Tommy Hilfiger - Camisa Social Xadrez', { id: 'aprovado-2026-09-11-tommy-hilfiger-camisa-social-xadrez', action: 'new-group' }],
  ['Ralph Lauren - Camisa Social Oxford', { id: 'aprovado-2026-07-12-ralph-lauren-camisa-social-oxford', action: 'merged-existing' }],
]);

function extractArray(source, name) {
  const marker = `const ${name} = `;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`${name} não encontrado`);
  const arrayStart = source.indexOf('[', start + marker.length);
  let depth = 0, inString = false, escaped = false;
  for (let i = arrayStart; i < source.length; i += 1) {
    const char = source[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') inString = true;
    else if (char === '[') depth += 1;
    else if (char === ']' && --depth === 0) return { value: JSON.parse(source.slice(arrayStart, i + 1)), start: arrayStart, end: i + 1 };
  }
  throw new Error(`${name} incompleto`);
}

function slugify(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function money(value) {
  const parsed = Number(String(value || '0').replace(/\./g, '').replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : 0;
}

function reviewedPublicationGroups(sourceGroups) {
  const result = [];
  for (const group of sourceGroups) {
    if (group.name === 'Ralph Lauren - Camiseta Supima') {
      const plainIds = new Set(['15837']);
      result.push({ ...group, products: group.products.filter(item => plainIds.has(String(item.supplierProductId))), identityReview: 'Supima lisa com pônei pequeno' });
      result.push({ ...group, id: `${group.id}-polo-sport`, name: 'Ralph Lauren - Camiseta Supima Polo Sport', siteBaseName: 'Camiseta Supima Polo Sport', products: group.products.filter(item => !plainIds.has(String(item.supplierProductId))), identityReview: 'Estampa frontal Polo Sport Ralph Lauren com bandeira' });
      continue;
    }
    if (group.name === 'Tommy Hilfiger - Calça Sarja') {
      const sportIds = new Set(['15125']);
      result.push({ ...group, products: group.products.filter(item => !sportIds.has(String(item.supplierProductId))), identityReview: 'Calça Sarja XE, família calcasarjaxe' });
      result.push({ ...group, id: `${group.id}-esporte-fino`, name: 'Tommy Hilfiger - Calça Sarja Esporte Fino', siteBaseName: 'Calça Sarja Esporte Fino', products: group.products.filter(item => sportIds.has(String(item.supplierProductId))), identityReview: 'Modelo Esporte Fino, família calcaesportexe; não agrupar com calcasarjaxe' });
      continue;
    }
    result.push({ ...group, identityReview: 'Marca, modelo, tecido e identidade visual conferidos pela referência do fornecedor' });
  }
  return result.filter(group => group.products.length);
}

function upsertGroup(groups, definition, queuedGroup, newProducts, productBySlug) {
  const newSlugs = newProducts.map(product => product.slug);
  for (const group of groups) {
    group.slugs = (group.slugs || []).filter(slug => !newSlugs.includes(slug));
    if (group.labels) for (const slug of newSlugs) delete group.labels[slug];
  }
  let group = groups.find(item => item.id === definition.id);
  if (!group) {
    group = { id: definition.id, name: queuedGroup.name, canonicalSlug: newSlugs[0], slugs: [], labels: {} };
    groups.unshift(group);
  }
  const seed = (definition.seed || []).filter(slug => productBySlug.has(slug));
  group.name ||= queuedGroup.name;
  group.slugs = [...new Set([...seed, ...(group.slugs || []), ...newSlugs])];
  group.canonicalSlug = group.canonicalSlug && group.slugs.includes(group.canonicalSlug) ? group.canonicalSlug : group.slugs[0];
  group.labels ||= {};
  for (const slug of group.slugs) {
    const product = productBySlug.get(slug);
    group.labels[slug] ||= product?.variantLabel || product?.name?.split(' - ').at(-1) || slug;
  }
  return group;
}

const queue = JSON.parse(fs.readFileSync(QUEUE, 'utf8'));
const photoManifest = JSON.parse(fs.readFileSync(PHOTOS, 'utf8'));
const correctedPhotos = {
  '15837': 'generated/aprovadas/site/2026-09-11/scp-15837-v2.webp',
  '16076': 'generated/aprovadas/site/2026-09-11/scp-16076-v2.webp',
  '16077': 'generated/aprovadas/site/2026-09-11/scp-16077-v2.webp',
  '16630': 'generated/aprovadas/site/2026-09-11/scp-16630-v2.webp',
  '16631': 'generated/aprovadas/site/2026-09-11/scp-16631-v2.webp',
};
for (const [id, photo] of Object.entries(correctedPhotos)) {
  if (!fs.existsSync(path.join(ROOT, photo))) throw new Error(`Foto corrigida da referência ${id} não encontrada.`);
  photoManifest.photos[id] = {
    ...photoManifest.photos[id],
    photo,
    status: 'foto-corrigida-identidade-validada',
    identityValidated: true,
    canvas: '1100x1100',
    framing: 'produto centralizado no padrão visual SCORSATTO',
  };
}
fs.writeFileSync(PHOTOS, JSON.stringify(photoManifest, null, 2) + '\n', 'utf8');
const publicationGroups = reviewedPublicationGroups(queue.groups);
let html = fs.readFileSync(INDEX, 'utf8');
const productsRange = extractArray(html, 'PRODUCTS');
let products = productsRange.value;
let groups = extractArray(html, 'PRODUCT_GROUPS').value;
const queuedIds = queue.groups.flatMap(group => group.products).map(product => String(product.supplierProductId));

if (queue.productCount !== 47 || queue.groupCount !== 11 || queuedIds.length !== 47) throw new Error('Fila esperada de 11 grupos / 47 peças não confere.');
for (const id of queuedIds) {
  const photo = photoManifest.photos?.[id]?.photo;
  if (!photo || !fs.existsSync(path.join(ROOT, photo))) throw new Error(`Foto pronta ausente para ${id}`);
}

const queuedSet = new Set(queuedIds);
const oldQueuedSlugs = new Set(products.filter(product => queuedSet.has(String(product.supplierProductId || ''))).map(product => product.slug));
for (const group of groups) {
  group.slugs = (group.slugs || []).filter(slug => !oldQueuedSlugs.has(slug));
  if (group.labels) for (const slug of oldQueuedSlugs) delete group.labels[slug];
}
products = products.filter(product => !queuedSet.has(String(product.supplierProductId || '')) && !queuedSet.has(String(product.id || '').replace(/^scp-/, '')));
const publishedGroups = [];

for (const queuedGroup of publicationGroups) {
  const price = PRICES.get(queuedGroup.name);
  const target = TARGETS.get(queuedGroup.name);
  if (!price || !target) throw new Error(`Regra comercial/agrupamento ausente: ${queuedGroup.name}`);
  const newProducts = queuedGroup.products.map(item => {
    const id = String(item.supplierProductId);
    const color = item.detectedColor || 'Cor sob consulta';
    const baseName = queuedGroup.siteBaseName || item.baseName || queuedGroup.name.split(' - ').slice(1).join(' - ');
    const slug = `${slugify(baseName)}-${slugify(color)}-${id}`;
    const cost = money(item.wholesalePrice);
    return {
      id: `scp-${id}`,
      supplierProductId: id,
      slug,
      name: `${baseName} - ${color}`,
      collection: queuedGroup.collection,
      price,
      cost,
      margin: Number((price - cost).toFixed(2)),
      supplierUrl: item.url,
      supplierName: 'Catálogo POA',
      status: 'sob-consulta',
      curated: true,
      lastCheckedAt: '2026-09-11',
      images: [photoManifest.photos[id].photo],
      imageCanvas: photoManifest.photos[id].canvas || 'padrão SCORSATTO',
      imageFraming: photoManifest.photos[id].framing || 'produto centralizado no padrão visual SCORSATTO',
      sizes: [...new Set(item.sizes || [])],
      stock: Object.fromEntries([...new Set(item.sizes || [])].map(size => [size, 1])),
      composition: 'Composição a confirmar no fornecedor antes da venda.',
      care: 'Consultar etiqueta original antes da lavagem. Preferir ciclo delicado e secagem à sombra.',
      tags: [...new Set([queuedGroup.brand, baseName, color, 'novidades', 'fornecedor-aprovado', 'foto-scorsatto-2026-09-10'])],
      internalNotes: `Aprovado por Alisson em 2026-09-11. Identidade revisada: ${queuedGroup.identityReview}.`,
      supplierGroupName: queuedGroup.name,
      variantLabel: color,
    };
  });
  products.push(...newProducts);
  const productBySlug = new Map(products.map(product => [product.slug, product]));
  groups = groups.filter(group => group.id !== 'json-sarja-1');
  const siteGroup = target.standalone ? null : upsertGroup(groups, target, queuedGroup, newProducts, productBySlug);
  publishedGroups.push({
    id: queuedGroup.id,
    name: queuedGroup.name,
    brand: queuedGroup.brand,
    collection: queuedGroup.collection,
    identityReview: queuedGroup.identityReview,
    identityReviewed: true,
    siteGroupId: siteGroup?.id || null,
    siteGroupAction: target.action,
    canonicalProductUrl: `/#produto-${encodeURIComponent(siteGroup?.canonicalSlug || newProducts[0].slug)}`,
    products: queuedGroup.products.map((item, index) => ({
      supplierProductId: String(item.supplierProductId), title: item.title, color: item.detectedColor,
      sizes: item.sizes || [], supplierUrl: item.url, referencePhoto: item.referencePath, photo: newProducts[index].images[0],
      imageCanvas: photoManifest.photos[String(item.supplierProductId)].canvas || 'padrão SCORSATTO',
      imageFraming: photoManifest.photos[String(item.supplierProductId)].framing || 'produto centralizado no padrão visual SCORSATTO',
      siteSlug: newProducts[index].slug, siteUrl: `/#produto-${encodeURIComponent(newProducts[index].slug)}`,
      price, status: 'publicado-no-site',
    })),
  });
}

const slugCounts = new Map();
for (const group of groups) for (const slug of group.slugs || []) slugCounts.set(slug, (slugCounts.get(slug) || 0) + 1);
for (const id of queuedIds) {
  const product = products.find(item => String(item.supplierProductId) === id);
  if (!product) throw new Error(`Produto não cadastrado: ${id}`);
  const expectedMembership = product.supplierProductId === '15125' ? 0 : 1;
  if ((slugCounts.get(product.slug) || 0) !== expectedMembership) throw new Error(`Agrupamento incorreto para ${product.slug}: esperado ${expectedMembership}, encontrado ${slugCounts.get(product.slug) || 0}`);
}
if (new Set(products.map(product => product.slug)).size !== products.length) throw new Error('Há slugs duplicados no catálogo.');
if (new Set(products.map(product => product.id)).size !== products.length) throw new Error('Há IDs duplicados no catálogo.');

html = html.slice(0, productsRange.start) + JSON.stringify(products) + html.slice(productsRange.end);
const updatedGroupsRange = extractArray(html, 'PRODUCT_GROUPS');
html = html.slice(0, updatedGroupsRange.start) + JSON.stringify(groups, null, 2).split('\n').map((line, index) => index ? `    ${line}` : line).join('\n') + html.slice(updatedGroupsRange.end);
fs.writeFileSync(INDEX, html, 'utf8');

const published = {
  day: '2026-09-11', sourceDay: queue.day, publishedAt: new Date().toISOString(),
  rule: 'Peças publicadas após aprovação humana; agrupamento exige mesma marca, modelo, tecido e identidade visual. Nome parecido nunca é suficiente.',
  status: 'publicado-no-site', groupCount: publishedGroups.length, productCount: queuedIds.length, groups: publishedGroups,
};
fs.writeFileSync(PUBLISHED, JSON.stringify(published, null, 2) + '\n', 'utf8');
fs.writeFileSync(PUBLISHED_DATED, JSON.stringify(published, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ products: products.length, groups: groups.length, publishedGroups: published.groupCount, publishedProducts: published.productCount }, null, 2));
