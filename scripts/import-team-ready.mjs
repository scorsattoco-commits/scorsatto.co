import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

export function arrayRange(html, name) {
  const marker = `const ${name} = `;
  const at = html.indexOf(marker);
  if (at < 0) throw Error(`Lista ausente: ${name}`);
  const start = html.indexOf('[', at + marker.length);
  let depth = 0, quoted = false, escaped = false;
  for (let i = start; i < html.length; i++) {
    const c = html[i];
    if (quoted) { if (escaped) escaped = false; else if (c === '\\') escaped = true; else if (c === '"') quoted = false; }
    else if (c === '"') quoted = true;
    else if (c === '[') depth++;
    else if (c === ']' && --depth === 0) return { start, end: i + 1, value: JSON.parse(html.slice(start, i + 1)) };
  }
  throw Error(`Lista incompleta: ${name}`);
}
const ref = v => String(v ?? '').trim().toUpperCase();
const norm = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const digest = v => crypto.createHash('sha256').update(v).digest('hex');
const assert = (ok, message) => { if (!ok) throw Error(message); };

export function planImport(html, manifest, verifyImage) {
  assert(manifest.version === 1 && manifest.source === 'scorsatto-team-workflow' && Array.isArray(manifest.groups), 'Manifesto de origem inválido');
  const originalProducts = arrayRange(html, 'PRODUCTS').value;
  const originalGroups = arrayRange(html, 'PRODUCT_GROUPS').value;
  const products = structuredClone(originalProducts), groups = structuredClone(originalGroups);
  const categories = new Set(arrayRange(html, 'CATEGORIES').value.map(c => c.collection).filter(Boolean));
  const byRef = new Map(), bySlug = new Map(products.map(p => [p.slug, p]));
  for (const p of products) {
    const key = ref(p.supplierProductId);
    if (!key) continue;
    assert(!byRef.has(key), `Referência já duplicada na loja: ${key}`);
    byRef.set(key, p);
  }
  const seen = new Set();
  for (const g of manifest.groups) for (const v of g.variants || []) {
    assert(ref(v.reference) && !seen.has(ref(v.reference)), `Referência ausente ou repetida no manifesto: ${v.reference}`);
    seen.add(ref(v.reference));
  }
  const report = { version: 1, sourceDigest: digest(JSON.stringify(manifest)), siteBeforeDigest: digest(html), results: [], pending: [] };
  for (const input of manifest.groups) {
    try {
      assert(input.id && input.identityConfirmed === true, 'Identidade do grupo não confirmada');
      assert(input.variants?.length && input.variants.every(v => v.stage === 'ready'), 'Grupo contém referências fora de Prontas para o site');
      const variants = input.variants;
      const existing = variants.filter(v => byRef.has(ref(v.reference)));
      const fresh = variants.filter(v => !byRef.has(ref(v.reference)));
      const memberships = new Set(existing.flatMap(v => groups.filter(g => g.slugs?.includes(byRef.get(ref(v.reference)).slug)).map(g => g.id)));
      assert(memberships.size <= 1, 'Referências existentes pertencem a grupos diferentes');
      const targetId = input.targetSiteGroupId || [...memberships][0] || `team-${norm(input.id)}`;
      let target = groups.find(g => g.id === targetId);
      if (input.targetSiteGroupId) assert(target, 'Grupo de destino informado não existe');
      if (memberships.size) assert(memberships.has(targetId), 'Destino diverge do grupo das referências existentes');
      if (existing.length && !memberships.size && fresh.length) throw Error('Referência existente sem grupo: associação requer conferência');
      if (!fresh.length) {
        for (const v of existing) { const p = byRef.get(ref(v.reference)); report.results.push({ reference: String(v.reference), action: 'already-present', slug: p.slug, url: `https://usescorsatto.com.br/#produto-${encodeURIComponent(p.slug)}` }); }
        continue;
      }
      assert(input.brand?.trim() && input.name?.trim() && categories.has(input.category), 'Marca, nome ou categoria existente ausente');
      if (!target) assert(!groups.some(g => norm(g.name) === norm(`${input.brand} - ${input.name}`)), 'Grupo de mesmo nome já existe: indicar targetSiteGroupId após conferir identidade');
      assert(typeof input.price === 'number' && Number.isFinite(input.price) && input.price > 0 && input.priceEvidence?.trim(), 'Preço de venda comprovado ausente');
      const colors = new Set((target?.slugs || []).map(s => norm(bySlug.get(s)?.variantLabel)).filter(Boolean));
      const additions = fresh.map(v => {
        assert(v.color?.trim() && !colors.has(norm(v.color)), `Cor já existente ou repetida: ${v.color}`);
        colors.add(norm(v.color));
        assert(Array.isArray(v.sizes) && v.sizes.length && v.sizes.every(s => typeof s === 'string' && s.trim()), `Tamanhos ausentes: ${v.reference}`);
        assert(v.description?.trim(), `Descrição comprovada ausente: ${v.reference}`);
        assert(v.image?.kind === 'edited' && v.image.reference === String(v.reference), `Foto editada da referência ausente: ${v.reference}`);
        verifyImage(v.image);
        const slug = `${norm(input.name)}-${norm(v.color)}-${norm(v.reference)}`;
        assert(!bySlug.has(slug) && !products.some(p => p.id === `team-${norm(v.reference)}`), `Slug/ID existente: ${v.reference}`);
        assert(!v.supplierUrl || new URL(v.supplierUrl).hostname === 'www.catalogopoa.com.br' || new URL(v.supplierUrl).hostname === 'catalogopoa.com.br', 'URL do fornecedor inválida');
        return {
          id: `team-${norm(v.reference)}`, supplierProductId: String(v.reference), slug,
          name: `${input.name} - ${v.color}`, collection: input.category, price: input.price,
          supplierUrl: v.supplierUrl || '', supplierName: 'Catálogo em equipe SCORSATTO',
          status: 'sob-consulta', curated: true, images: [v.image.path], sizes: [...new Set(v.sizes)], stock: {},
          description: v.description, composition: v.composition || '', care: v.care || '',
          tags: [input.brand, input.name, v.color], variantLabel: v.color,
          supplierGroupId: input.id, supplierCode: v.supplierCode || '',
        };
      });
      if (!target) { target = { id: targetId, name: `${input.brand} - ${input.name}`, canonicalSlug: additions[0].slug, slugs: [], labels: {} }; groups.push(target); }
      for (const p of additions) {
        products.push(p); byRef.set(ref(p.supplierProductId), p); bySlug.set(p.slug, p);
        target.slugs.push(p.slug); target.labels ||= {}; target.labels[p.slug] = p.variantLabel;
        report.results.push({ reference: p.supplierProductId, action: 'added', slug: p.slug, url: `https://usescorsatto.com.br/#produto-${encodeURIComponent(p.slug)}` });
      }
      for (const v of existing) { const p = byRef.get(ref(v.reference)); report.results.push({ reference: String(v.reference), action: 'already-present', slug: p.slug, url: `https://usescorsatto.com.br/#produto-${encodeURIComponent(p.slug)}` }); }
    } catch (error) { report.pending.push({ groupId: input.id, references: (input.variants || []).map(v => v.reference), reason: error.message }); }
  }
  assert(originalProducts.every((p, i) => JSON.stringify(products[i]) === JSON.stringify(p)), 'Produto existente alterado');
  for (const old of originalGroups) {
    const current = groups.find(g => g.id === old.id);
    assert(old.slugs.every((s, i) => current.slugs[i] === s), 'Ordem de cores existente alterada');
    for (const [key, val] of Object.entries(old)) if (key !== 'slugs' && key !== 'labels') assert(JSON.stringify(current[key]) === JSON.stringify(val), 'Metadado de grupo existente alterado');
    for (const [key, val] of Object.entries(old.labels || {})) assert(current.labels[key] === val, 'Rótulo existente alterado');
  }
  let output = html;
  for (const [name, value] of [['PRODUCTS', products], ['PRODUCT_GROUPS', groups]]) { const r = arrayRange(output, name); if (JSON.stringify(value) !== JSON.stringify(r.value)) output = output.slice(0, r.start) + JSON.stringify(value).replace(/</g, '\\u003c') + output.slice(r.end); }
  report.added = report.results.filter(r => r.action === 'added').length;
  report.alreadyPresent = report.results.filter(r => r.action === 'already-present').length;
  report.siteAfterDigest = digest(output);
  // A result is a publication plan, never proof of deployment or permission to mark No site.
  report.publicationVerified = false;
  return { html: output, report };
}

export function verifyPng(root, image) {
  assert(/^generated\/catalogo-equipe\/[A-Za-z0-9_/-]+\.png$/.test(image.path || ''), 'Foto deve estar em generated/catalogo-equipe/*.png');
  const resolved = path.resolve(root, image.path);
  assert(resolved.startsWith(path.resolve(root) + path.sep), 'Caminho de foto inválido');
  const data = fs.readFileSync(resolved);
  assert(data.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10])), 'Arquivo não é PNG');
  assert(data.length >= 24 && data.readUInt32BE(16) === 1100 && data.readUInt32BE(20) === 1100, 'PNG deve ter 1100x1100');
  assert(/^[a-f0-9]{64}$/.test(image.sha256 || '') && digest(data) === image.sha256, 'Hash da foto divergente');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), input = args[0];
  assert(input && args.every((a, i) => i === 0 || a === '--apply'), 'Uso: node scripts/import-team-ready.mjs manifesto.json [--apply]');
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const index = path.join(root, 'index.html'), html = fs.readFileSync(index, 'utf8');
  const manifest = JSON.parse(fs.readFileSync(input, 'utf8').replace(/^\uFEFF/, ''));
  const result = planImport(html, manifest, image => verifyPng(root, image));
  fs.mkdirSync(path.join(root, '.local-data'), { recursive: true });
  fs.writeFileSync(path.join(root, '.local-data/team-publication-report.json'), JSON.stringify(result.report, null, 2) + '\n');
  if (args.includes('--apply') && result.report.added) {
    assert(fs.readFileSync(index, 'utf8') === html, 'Site mudou durante a preparação');
    fs.writeFileSync(path.join(root, '.local-data/index-before-team-import.html'), html);
    const temp = `${index}.team-import.tmp`;
    fs.writeFileSync(temp, result.html); fs.renameSync(temp, index);
  }
  console.log(JSON.stringify(result.report, null, 2));
}

