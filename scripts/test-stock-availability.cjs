const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { createContext, runInContext } = require('node:vm');
const assert = require('node:assert/strict');

const html = readFileSync(join(__dirname, '../index.html'), 'utf8');
for (const [, attributes, source] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
  if (!attributes.includes('application/ld+json') && source.trim()) new Function(source);
}
const purchase = readFileSync(join(__dirname, '../purchase-experience.js'), 'utf8');
const context = createContext({
  assert, window: {}, PRODUCTS: [], active: 'gola-polo',
  approvedProductGroups: [], normalize: value => value.toLowerCase(),
  variantColorName: p => p.color,
});
runInContext('const sortSizes = values => [...new Set(values)];', context);
runInContext(purchase.slice(0, purchase.indexOf('// Local preview')), context);
runInContext(html.slice(html.indexOf('    const isAvailableNow ='), html.indexOf('    const visibleProducts =')), context);
runInContext(html.slice(html.indexOf('    function variantOptionSizes('), html.indexOf('    function productVariants(')), context);
runInContext(`
 const options = { color:'preto',collection:'gola-polo',supplierProductId:'17442',
  status:'sob-consulta',supplierUrl:'https://www.catalogopoa.com.br/polo-17442',
  sizes:['P','M','G','GG'],stock:{P:1,M:1,G:1,GG:1} };
 const supplier = {...options,slug:'polo-fornecedor'};
 const otherColor = {...options,slug:'polo-azul',supplierProductId:'17443',color:'azul',status:'disponivel',sizes:['P'],stock:{P:1}};
 const local = {...options,slug:'polo-local',supplierUrl:'estoque-proprio-scorsatto',status:'disponivel',sizes:['G'],stock:{G:1}};
 PRODUCTS.push(supplier,otherColor,local);
 assert.equal(variantForSize(supplier,'G'),local);
 assert.equal(variantForSize(supplier,'M'),supplier);
 local.supplierProductId='SC-005';
 approvedProductGroups.push(
  {slugs:[supplier.slug,otherColor.slug],labels:{[supplier.slug]:'Preto',[otherColor.slug]:'Azul'}},
  {slugs:[supplier.slug,local.slug],labels:{[supplier.slug]:'Preto',[local.slug]:'Preto'}}
 );
 assert.equal(variantForSize(supplier,'G'),local);
 assert.equal(sizeSelectionFeedback(supplier,'G'),'Tamanho G · Pronta entrega');
 assert.equal(sizeSelectionFeedback(supplier,'M'),'Tamanho M · Sob consulta');
 assert.deepEqual(variantOptionSizes(supplier),['P','M','G','GG']);
 active='disponiveis-agora';
 assert.deepEqual(variantOptionSizes(local),['G']);
 assert.equal(variantForSize(local,'M'),undefined);
 active='gola-polo';
 window.scorsattoSupplierUnavailable=[supplier.supplierUrl];
 assert.ok(isPublicProduct(supplier));
 assert.deepEqual(variantOptionSizes(supplier),['G']);
 local.status='vendido';
 assert.ok(!isPublicProduct(supplier));
 assert.ok(isPublicProduct(otherColor));
 supplier.localStock={G:2};
 assert.ok(isPublicProduct(supplier));
 assert.equal(orderableQuantity(supplier,'G'),2);
 assert.equal(orderableQuantity(supplier,'M'),0);
 window.scorsattoSupplierUnavailable=[];
 assert.equal(variantForSize(supplier,'M'),supplier);
 assert.equal(physicalStockQuantity(supplier,'M'),0);
 active='disponiveis-agora';
 assert.deepEqual(variantOptionSizes(supplier),['G']);
 supplier.hidden=true;
 assert.ok(!isPublicProduct(supplier));
`, context);
console.log('Estoque por tamanho, vínculo exato, ocultação, reposição e visibilidade manual validados.');
