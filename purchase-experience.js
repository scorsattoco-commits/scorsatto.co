// SCORSATTO product purchase and size-aware recommendations.
function kitAvailableSizes(product){return (product?.sizes||[]).filter(size=>Number(product.stock?.[size]||0)>0);}
function sizeSelectionFeedback(product,size){return 'Tamanho '+size+(isAvailableNow(variantForSize(product,size))?' · Pronta entrega':' · Sob consulta');}
// Local preview: stock-checked, explicit additions without opening the bag.
let combinationState=null;
function refreshCombination(){}
function requestQuickSize(grid,status,message='Escolha seu tamanho para adicionar ↓'){
 status.textContent=message;grid.classList.add('choose-size-now');
 grid.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 grid.querySelector('button')?.focus({preventScroll:true});
}
function guideNextComplement(from){
 const section=productDetail.querySelector('.quick-complements');if(!section)return;
 const cards=[...section.querySelectorAll('.quick-piece[data-quick-slot]')];
 const next=cards.find(card=>card!==from&&!card.dataset.addedSize);
 cards.forEach(card=>card.classList.remove('is-next-choice'));
 if(next){next.classList.add('is-next-choice');next.querySelector('[role="status"]').textContent='Combine com sua escolha. Selecione o tamanho.';next.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
 else {const bag=section.querySelector('[data-fast-bag]');bag.scrollIntoView({block:'center'});bag.focus({preventScroll:true});}
}
function renderQuickPieces(base){
 const bottom=['calcas','bermudas'].includes(base.collection),outer=['jaquetas','casacos','sueteres'].includes(base.collection);
 const groups=bottom?[['camisetas','gola-polo'],['jaquetas','sueteres']]:outer?[['camisetas','gola-polo'],['calcas']]:[['calcas','bermudas'],['jaquetas','sueteres']];
 const slots=[{product:base,size:null}];
 groups.forEach(group=>{
  const pool=visibleProducts().filter(p=>p.slug!==base.slug&&group.includes(p.collection)&&isAvailableNow(p)&&kitAvailableSizes(p).some(size=>Number(p.stock?.[size]||0)>(cart.find(item=>item.key===cartKey(p.slug,size))?.quantity||0))&&productImage(p));
  const previous=combinationState?.slots.slice(1).map(slot=>slot.product.slug)||[];
  const alternatives=pool.filter(p=>!previous.includes(p.slug)&&!cart.some(item=>item.slug===p.slug));
  const options=alternatives.length?alternatives:pool.filter(p=>!previous.includes(p.slug));
  const choices=options.length?options:pool;
  if(choices.length)slots.push({product:choices[Math.floor(Math.random()*choices.length)],size:null});
 });
 combinationState={base:base.slug,slots};
 return slots.length>1?`<section class="combination quick-complements" aria-label="Combina com sua peça"><h3>Combina com sua peça</h3><div class="quick-pieces">${slots.slice(1).map((slot,i)=>{const p=slot.product;return `<article class="quick-piece" data-quick-slot="${i+1}"><img src="${safeHtml(productImage(p))}" alt="${safeHtml(displayProductName(p))}" loading="lazy" decoding="async"><div><h4>${safeHtml(displayProductName(p))}</h4><p>${safeHtml(variantColorName(p))}</p><strong>${currency.format(p.price)}</strong><div class="quick-sizes" role="group" aria-label="Tamanho de ${safeHtml(displayProductName(p))}">${kitAvailableSizes(p).map(size=>`<button type="button" data-fast-size="${safeHtml(size)}" aria-pressed="false">${safeHtml(size)}</button>`).join('')}</div><button type="button" class="primary-btn" data-fast-add disabled>Adicionar</button><small role="status" aria-live="polite">Escolha o tamanho</small></div></article>`;}).join('')}</div><button type="button" class="quick-bag" data-fast-bag>Ver minha sacola →</button></section>`:'';
}
function renderCombination(base){
 const html=renderQuickPieces(base);
 return html.replace('<h3>Combina com sua peça</h3>','<h3>Sua escolha combina com estas peças.</h3>').replace('</section>','<button type="button" class="quick-bag quick-refresh" data-fast-refresh>Ver outras combinações ↻</button><small class="quick-refresh-feedback" role="status" aria-live="polite"></small></section>');
}
function quickAddProduct(p,size){
 if(!p||!size||!isPublicProduct(p))return 'Esta peça não está disponível para seleção.';
 const key=cartKey(p.slug,size),current=cart.find(item=>item.key===key);
 if(!kitAvailableSizes(p).includes(size))return 'Este tamanho não está disponível. Escolha outro.';
 if(Number(p.stock?.[size]||0)<(current?.quantity||0)+1)return current?'Já está na sacola ✓':'Este tamanho não está disponível. Escolha outro.';
 if(current)current.quantity++;else cart.push({key,slug:p.slug,size,quantity:1});
 saveCart();recordCustomerEvent('add_to_cart',p.slug,{size,quantity:1});return null;
}
function handleCombinationClick(event){
 const button=event.target.closest('.combination button');if(!button)return false;
 if(button.hasAttribute('data-fast-bag')){openCart();return true;}
 if(button.hasAttribute('data-fast-refresh')){
  const section=button.closest('.quick-complements'),oldSlots=combinationState.slots;
  const oldCards=[...section.querySelectorAll('.quick-piece')];
  section.outerHTML=renderCombination(PRODUCTS.find(p=>p.slug===combinationState.base));
  const next=productDetail.querySelector('.quick-complements');
  if(!next)return true;
  next.querySelectorAll('[data-fast-add]').forEach(button=>button.disabled=false);
  let changed=false;
  combinationState.slots.slice(1).forEach((slot,index)=>{
   const oldIndex=oldSlots.findIndex(old=>old.product.slug===slot.product.slug);
   if(oldIndex>0){slot.size=oldSlots[oldIndex].size;const card=oldCards[oldIndex-1];card.dataset.quickSlot=String(index+1);next.querySelectorAll('.quick-piece')[index].replaceWith(card);}
   else changed=true;
  });
  next.querySelector('.quick-refresh-feedback').textContent=changed?'Novas sugestões. Sua sacola continua igual.':'Estas são as opções disponíveis no momento.';
  next.querySelector('[data-fast-refresh]').focus({preventScroll:true});
  return true;
 }
 const card=button.closest('[data-quick-slot]');if(!card)return true;
 const slot=combinationState.slots[Number(card.dataset.quickSlot)],status=card.querySelector('[role="status"]'),add=card.querySelector('[data-fast-add]');
 if(button.dataset.fastSize){slot.size=button.dataset.fastSize;card.querySelector('.quick-sizes').classList.remove('choose-size-now');card.querySelectorAll('[data-fast-size]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.fastSize===slot.size)));add.disabled=false;add.textContent='Adicionar';status.textContent='Tamanho '+slot.size;}
 if(button.hasAttribute('data-fast-add')){
  if(!slot.size){requestQuickSize(card.querySelector('.quick-sizes'),status);return true;}
  if(card.dataset.addedSize===slot.size){guideNextComplement(card);return true;}
  const error=quickAddProduct(slot.product,slot.size);status.textContent=error||'Adicionado à sua sacola';
  const ok=!error||error==='Já está na sacola ✓';add.textContent=ok?'Na sacola ✓ · Continuar':'Escolher outro tamanho';
  if(ok){card.dataset.addedSize=slot.size;guideNextComplement(card);}else requestQuickSize(card.querySelector('.quick-sizes'),status,error);
 }
 return true;
}
function setupQuickPurchase(product){
 document.querySelector('#quickPurchaseBar')?.remove();
 const action=productDetail.querySelector('#detailAdd');if(!action)return;
 action.disabled=!variantOptionSizes(product).length;
 if(!action.disabled)action.textContent='Adicionar à sacola';
 productDetail.querySelectorAll('[data-fast-add]').forEach(button=>button.disabled=false);
 const feedback=document.createElement('p');feedback.id='quickMainFeedback';feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');action.closest('.detail-actions').after(feedback);
 const bar=document.createElement('div');bar.id='quickPurchaseBar';bar.innerHTML=`<span>${currency.format(product.price)}</span><button type="button" class="primary-btn">Escolher tamanho</button>`;productDetailSection.append(bar);
 const sync=()=>{const visible=productDetailSection.classList.contains('open')&&action.getBoundingClientRect().bottom<productDetailSection.getBoundingClientRect().top;bar.classList.toggle('is-visible',visible);const b=bar.querySelector('button');b.textContent=selectedDetailSize?action.textContent:'Escolher tamanho';b.disabled=!!selectedDetailSize&&action.disabled;};
 bar.querySelector('button').addEventListener('click',()=>{action.click();sync();});
 productDetailSection.onscroll=sync;productDetail.onclick=()=>{if(selectedDetailSize)productDetail.querySelector('.size-grid')?.classList.remove('choose-size-now');sync();};sync();
}
function showPurchaseComplements(){
 const section=productDetail.querySelector('.quick-complements');if(!section)return;
 const heading=section.querySelector('h3');heading.tabIndex=-1;heading.focus({preventScroll:true});
 section.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
}
function quickMainPurchase(product){
 if(!selectedDetailSize){requestQuickSize(productDetail.querySelector('.size-grid'),productDetail.querySelector('#sizeSelectionFeedback'));return;}
 productDetail.querySelector('.size-grid').classList.remove('choose-size-now');
 const target=variantForSize(product,selectedDetailSize);
 if(productDetail.querySelector('#detailAdd').dataset.addedSize===selectedDetailSize&&cart.some(item=>item.key===cartKey(target.slug,selectedDetailSize))){showPurchaseComplements();return;}
 const error=quickAddProduct(target,selectedDetailSize),button=productDetail.querySelector('#detailAdd');
 const ok=!error||error==='Já está na sacola ✓';button.textContent=ok?'Na sacola ✓ · Ver complementos':'Escolher outro tamanho';button.disabled=false;
 if(ok)button.dataset.addedSize=selectedDetailSize;
 productDetail.querySelector('#quickMainFeedback').textContent=error||(isAvailableNow(target)?'Na sua sacola. Continue escolhendo.':'Na sacola · disponibilidade e prazo serão confirmados no atendimento.');
 if(ok){
  showPurchaseComplements();
  const section=productDetail.querySelector('.quick-complements');
  const next=[...(section?.querySelectorAll('.quick-piece[data-quick-slot]')||[])].find(card=>!card.dataset.addedSize);
  if(next){
   section.querySelector('h3').textContent='Complete sua escolha.';
   section.querySelectorAll('.is-next-choice').forEach(card=>card.classList.remove('is-next-choice'));
   next.classList.add('is-next-choice');
   next.querySelector('[role="status"]').textContent='Escolha seu tamanho para adicionar também.';
   const heading=section.querySelector('h3');heading.tabIndex=-1;heading.focus({preventScroll:true});
   section.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
 }
}


// Local recommendation rules, not a fit prediction or inventory reservation.
let fitPreferences={top:null,bottom:null};
const fitSeen=new Map();
const fitOriginalClick=handleCombinationClick;
function fitBottom(p){return ['calcas','bermudas'].includes(p.collection);}
function fitSizes(p){return kitAvailableSizes(p).filter(size=>Number(p.stock?.[size]||0)>(cart.find(i=>i.key===cartKey(p.slug,size))?.quantity||0));}
function fitText(value){return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}
function fitScore(base,p){
 const color=fitText(variantColorName(p)),baseColor=fitText(variantColorName(base));
 const neutral=/preto|branco|off|gelo|cinza|marinho|bege|caqui/.test(color);
 const earth=/marrom|caramelo|bege|caqui|verde/.test(baseColor)&&/branco|off|gelo|bege|marinho|caqui/.test(color);
 const pattern=/xadrez|estamp|listr/.test(fitText(p.name));
 const basePattern=/xadrez|estamp|listr/.test(fitText(base.name));
 if(pattern&&basePattern)return -1;
 if(/social/.test(base.collection)&&/moletom|capuz|esport/.test(fitText(p.name)))return -1;
 return (neutral?4:0)+(earth?3:0)+(color!==baseColor?1:0)+(pattern?0:2);
}
function fitPool(base,group){return visibleProducts().filter(p=>p.slug!==base.slug&&group.includes(p.collection)&&productImage(p)&&fitSizes(p).length&&fitScore(base,p)>=0);}
function fitPick(base,group,old){
 const desired=fitPreferences[group.some(c=>['calcas','bermudas'].includes(c))?'bottom':'top'];
 const isBottomGroup=group.some(c=>['calcas','bermudas'].includes(c));
 if(isBottomGroup!==fitBottom(base)&&!desired)return null;
 let pool=fitPool(base,group).filter(p=>!desired||fitSizes(p).includes(desired));
 const key=base.slug+'|'+group.join(',')+'|'+desired;
 let seen=fitSeen.get(key)||new Set();
 let unseen=pool.filter(p=>!seen.has(p.slug));
 if(!unseen.length){seen=new Set(old?[old.slug]:[]);unseen=pool.filter(p=>!seen.has(p.slug));}
 if(unseen.length)pool=unseen;
 const different=pool.filter(p=>p.slug!==old?.slug);if(different.length)pool=different;
 const ready=pool.filter(isAvailableNow);if(ready.length)pool=ready;
 const fresh=pool.filter(p=>!cart.some(i=>i.slug===p.slug));if(fresh.length)pool=fresh;
 pool.sort((a,b)=>fitScore(base,b)-fitScore(base,a));
 const best=pool.filter(p=>fitScore(base,p)>=fitScore(base,pool[0]||p)-1);
 const chosen=best.length?best[Math.floor(Math.random()*best.length)]:null;
 if(chosen)seen.add(chosen.slug);fitSeen.set(key,seen);return chosen;
}
function fitRender(){
 const s=combinationState,base=s.slots[0].product;
 const topSizes=[...new Set(s.groups.filter(g=>!g.some(c=>['calcas','bermudas'].includes(c))).flatMap(g=>fitPool(base,g).flatMap(fitSizes)))].sort((a,b)=>['PP','P','M','G','GG','XG','XXG'].indexOf(a)-['PP','P','M','G','GG','XG','XXG'].indexOf(b));
 const bottomSizes=[...new Set(s.groups.filter(g=>g.some(c=>['calcas','bermudas'].includes(c))).flatMap(g=>fitPool(base,g).flatMap(fitSizes)))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
 return `<section class="combination quick-complements" aria-label="Complementos por tamanho"><h3>Complete sua escolha.</h3><p class="fit-note">${fitPreferences.top?'Sugestões no tamanho '+safeHtml(fitPreferences.top)+'. Confirme o caimento de cada marca.':'Escolha o tamanho principal para refinar as sugestões.'}</p>${fitBottom(base)&&topSizes.length?`<div class="fit-preference"><p>Qual tamanho você usa nas peças de cima?</p><div class="quick-sizes" role="group" aria-label="Seu tamanho em camisetas e camisas">${topSizes.map(size=>`<button type="button" data-fit-top="${safeHtml(size)}" aria-pressed="${fitPreferences.top===size}">${safeHtml(size)}</button>`).join('')}</div></div>`:''}${!fitBottom(base)&&bottomSizes.length?`<div class="fit-preference"><p>Seu tamanho em calças e bermudas</p><div class="quick-sizes" role="group" aria-label="Seu tamanho em peças de baixo">${bottomSizes.map(size=>`<button type="button" data-fit-bottom="${safeHtml(size)}" aria-pressed="${fitPreferences.bottom===size}">${safeHtml(size)}</button>`).join('')}</div></div>`:''}<div class="quick-pieces">${s.slots.slice(1).map((slot,i)=>{
 const p=slot.product;if(!p){const lower=s.groups[i].some(c=>['calcas','bermudas'].includes(c));const wanted=fitPreferences[lower?'bottom':'top'];return `<article class="quick-piece fit-empty"><p>${wanted?'Nenhuma opção nesta categoria no tamanho '+safeHtml(wanted)+'.':'Escolha acima seu tamanho '+(lower?'de calça ou bermuda':'nas peças de cima')+' para ver as sugestões.'}</p></article>`;}
 const desired=fitPreferences[fitBottom(p)?'bottom':'top'];
 return `<article class="quick-piece" data-quick-slot="${i+1}" ${slot.added?'data-added-size="'+safeHtml(slot.size)+'"':''}><img src="${safeHtml(productImage(p))}" alt="${safeHtml(displayProductName(p))}" loading="lazy"><div><h4>${safeHtml(displayProductName(p))}</h4><p>${safeHtml(variantColorName(p))} · ${currency.format(p.price)}</p><p class="fit-availability">${isAvailableNow(p)?'Pronta entrega':'Sob consulta · disponibilidade a confirmar'}</p><p class="fit-note">${/preto|branco|off|gelo|cinza|marinho|bege|caqui/.test(fitText(variantColorName(p)))?'Uma base neutra para acompanhar sua escolha.':'Uma alternativa de cor para o conjunto.'}</p><div class="quick-sizes" role="group" aria-label="Tamanho de ${safeHtml(displayProductName(p))}">${kitAvailableSizes(p).filter(size=>!desired||size===desired).map(size=>`<button type="button" data-fast-size="${safeHtml(size)}" aria-pressed="${slot.size===size}">${safeHtml(size)}</button>`).join('')}</div><button type="button" class="primary-btn" data-fast-add>${slot.added?'Na sacola ✓ · Continuar':isAvailableNow(p)?'Adicionar':'Adicionar sob consulta'}</button><small role="status" aria-live="polite">${slot.size?'Tamanho '+safeHtml(slot.size):'Confirme seu tamanho'}</small><button type="button" class="quick-bag" data-fit-swap="${i+1}" ${fitHasAlternative(i+1)?'':'disabled'}>${fitHasAlternative(i+1)?'Ver outra opção ↻':'Sem outra opção neste tamanho'}</button></div></article>`;
 }).join('')}</div><button type="button" class="quick-bag" data-fast-bag>Ver minha sacola →</button><button type="button" class="quick-bag quick-refresh" data-fast-refresh>Ver outras combinações ↻</button><small class="quick-refresh-feedback" role="status" aria-live="polite"></small></section>`;
}
renderCombination=function(base){
 const bottom=fitBottom(base),outer=['jaquetas','casacos','sueteres'].includes(base.collection);
 const groups=bottom?[['camisetas','gola-polo'],['jaquetas','sueteres']]:outer?[['camisetas','gola-polo'],['calcas']]:[['calcas','bermudas'],['jaquetas','sueteres']];
 if(selectedDetailSize)fitPreferences[bottom?'bottom':'top']=selectedDetailSize;
 combinationState={base:base.slug,groups,slots:[{product:base,size:null},...groups.map(group=>({product:fitPick(base,group),size:null}))]};
 return fitRender();
};
function fitHasAlternative(index){
 const s=combinationState,slot=s.slots[index];
 const desired=fitPreferences[s.groups[index-1].some(c=>['calcas','bermudas'].includes(c))?'bottom':'top'];
 return fitPool(s.slots[0].product,s.groups[index-1]).some(p=>p.slug!==slot.product?.slug&&(!desired||fitSizes(p).includes(desired)));
}
function fitUpdate(index){
 const s=combinationState,base=s.slots[0].product;
 s.slots.slice(1).forEach((slot,i)=>{if(index!==undefined&&index!==i+1)return;const p=fitPick(base,s.groups[i],slot.product);if(p?.slug!==slot.product?.slug)s.slots[i+1]={product:p,size:null};});
 productDetail.querySelector('.quick-complements').outerHTML=fitRender();
}
refreshCombination=function(){
 if(!combinationState?.groups)return;
 const base=combinationState.slots[0].product;if(selectedDetailSize)fitPreferences[fitBottom(base)?'bottom':'top']=selectedDetailSize;
 combinationState.slots.slice(1).forEach((slot,i)=>{
  const desired=fitPreferences[combinationState.groups[i].some(c=>['calcas','bermudas'].includes(c))?'bottom':'top'];
  if(!slot.product||desired&&!fitSizes(slot.product).includes(desired))combinationState.slots[i+1]={product:fitPick(base,combinationState.groups[i]),size:null};
  else if(desired&&slot.size!==desired){slot.size=null;slot.added=false;}
 });
 productDetail.querySelector('.quick-complements').outerHTML=fitRender();
};
handleCombinationClick=function(event){
 const b=event.target.closest('.combination button');if(!b)return false;
 if(b.hasAttribute('data-fit-top')){fitPreferences.top=b.dataset.fitTop;refreshCombination();return true;}
 if(b.hasAttribute('data-fit-bottom')){fitPreferences.bottom=b.dataset.fitBottom||null;refreshCombination();return true;}
 if(b.hasAttribute('data-fit-swap')||b.hasAttribute('data-fast-refresh')){
  const index=b.hasAttribute('data-fit-swap')?Number(b.dataset.fitSwap):undefined;
  const old=combinationState.slots.map(s=>s.product?.slug).join('|');fitUpdate(index);
  productDetail.querySelector('.quick-refresh-feedback').textContent=old===combinationState.slots.map(s=>s.product?.slug).join('|')?'Sem outra opção compatível no momento.':'Sugestões atualizadas. Sua sacola continua igual.';
  productDetail.querySelector(index?'[data-fit-swap="'+index+'"]':'[data-fast-refresh]')?.focus({preventScroll:true});return true;
 }
 const card=b.closest('[data-quick-slot]');
 if(card&&b.hasAttribute('data-fast-add')){
  const slot=combinationState.slots[Number(card.dataset.quickSlot)],p=slot.product;
  if(!isAvailableNow(p)){
   const status=card.querySelector('[role="status"]');
   if(!slot.size){requestQuickSize(card.querySelector('.quick-sizes'),status);return true;}
   if(!isPublicProduct(p)||!kitAvailableSizes(p).includes(slot.size)){status.textContent='Esta opção não está disponível para seleção.';return true;}
   const key=cartKey(p.slug,slot.size);
   if(!cart.some(i=>i.key===key)){cart.push({key,slug:p.slug,size:slot.size,quantity:1});saveCart();}
   slot.added=true;card.dataset.addedSize=slot.size;b.textContent='Na sacola ✓ · Continuar';
   status.textContent='Selecionada sob consulta. Confirme disponibilidade antes de comprar.';
   guideNextComplement(card);return true;
  }
 }
 const result=fitOriginalClick(event);
 if(card){const slot=combinationState.slots[Number(card.dataset.quickSlot)];slot.added=card.dataset.addedSize===slot.size;}
 return result;
};
document.addEventListener('DOMContentLoaded',()=>{
const fitOriginalRenderCart=renderCart;
renderCart=function(){
 fitOriginalRenderCart();
 let note=document.getElementById('fitCartConsultation');
 if(!note){note=document.createElement('p');note.id='fitCartConsultation';note.setAttribute('role','status');document.getElementById('checkout').before(note);}
 const pending=cart.filter(item=>{const p=PRODUCTS.find(p=>p.slug===item.slug);return p&&!isAvailableNow(p);});
 note.textContent=pending.length?'Itens sob consulta: '+pending.map(item=>displayProductName(PRODUCTS.find(p=>p.slug===item.slug))+' ('+item.size+')').join(', ')+'. Disponibilidade e prazo serão confirmados no atendimento.':'';
};
renderCart();
});


document.addEventListener('DOMContentLoaded',()=>{
 document.addEventListener('click',event=>{
  const link=event.target.closest('a[href^="#"]');
  if(link&&!link.getAttribute('href').startsWith('#produto-')&&productDetailSection.classList.contains('open'))closeProduct(false);
 },true);
 window.addEventListener('hashchange',()=>{if(!location.hash.startsWith('#produto-')&&productDetailSection.classList.contains('open'))closeProduct(false);});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&productDetailSection.classList.contains('open')&&!document.querySelector('.cart-drawer.open,.account-drawer.open'))closeProduct();});
 window.addEventListener('resize',()=>{document.documentElement.style.setProperty('--purchase-menu-height',Math.ceil(topbar.getBoundingClientRect().height)+'px');},{passive:true});
});
