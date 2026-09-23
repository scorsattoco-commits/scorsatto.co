/* Private, browser-local draft editor. No public content write endpoint. */
(()=>{
 'use strict';
 const owners=new Set(['alisson@scorsatto.co','miguel@scorsatto.co']);
 const fields=[
 ['signature','Assinatura inicial','#heroLogo .hero-signature'],
 ['ready','Botão de pronta entrega','#heroLogo [data-filter-link="disponiveis-agora"]'],
 ['collection','Botão da coleção','#heroLogo [data-filter-link="todos"]'],
 ['aboutTitle','Título Sobre','#sobre h2'],
 ['about1','Apresentação','#sobre .about-copy p:nth-child(1)'],
 ['about2','Curadoria','#sobre .about-copy p:nth-child(2)'],
 ['about3','Atendimento na apresentação','#sobre .about-copy p:nth-child(3)'],
 ['how','Título Como funciona','#entrega-trocas h2'],
 ...[1,2,3].flatMap(n=>[[`step${n}title`,`Etapa ${n} — título`,`#entrega-trocas .policy-grid:first-of-type .policy-card:nth-child(${n}) strong`],[`step${n}`,`Etapa ${n} — texto`,`#entrega-trocas .policy-grid:first-of-type .policy-card:nth-child(${n}) span`]]),
 ['delivery','Texto de entrega','#entrega span'],['returns','Texto de trocas','#trocas span']
 ];
 // Policy grids follow the heading div, so identify the first grid explicitly.
 fields.forEach(f=>f[2]=f[2].replace('.policy-grid:first-of-type','.section-head + .policy-grid'));
 const blocks=[['produtos','Coleção'],['account','Conta'],['sobre','Sobre']];
 let baseline=null,draft=null,userId=null,overlay=null,preview=false;
 const getBlock=id=>id==='account'?document.querySelector('main > .account-strip'):document.getElementById(id);
 function capture(){return {texts:Object.fromEntries(fields.map(([id,,sel])=>[id,document.querySelector(sel)?.textContent||''])),order:blocks.map(([id])=>id)};}
 function normalize(value){const out=structuredClone(baseline);for(const [id]of fields)if(typeof value?.texts?.[id]==='string')out.texts[id]=value.texts[id].slice(0,1500);if(Array.isArray(value?.order)&&value.order.length===3&&new Set(value.order).size===3&&value.order.every(id=>blocks.some(b=>b[0]===id)))out.order=[...value.order];return out;}
 async function authorized(){if(typeof db==='undefined'||!db||!isAdminAccount())throw Error('Entre com a conta administrativa do Alisson ou Miguel.');const {data,error}=await db.auth.getUser();if(error||!data.user||!owners.has(String(data.user.email||'').toLowerCase())||data.user.id!==account?.id&&data.user.email?.toLowerCase()!==account?.email?.toLowerCase())throw Error('Sua sessão não tem acesso a este editor.');return data.user.id;}
 function apply(value){for(const [id,,sel]of fields){const el=document.querySelector(sel);if(el)el.textContent=value.texts[id];}const main=document.querySelector('main');value.order.forEach(id=>{const el=getBlock(id);if(el)main.append(el);});}
 let anchors=[];
 function restore(){if(!preview)return;for(const [id,,sel]of fields){const el=document.querySelector(sel);if(el)el.textContent=baseline.texts[id];}anchors.forEach(([node,anchor])=>anchor.parentNode?.insertBefore(node,anchor));anchors.forEach(([,anchor])=>anchor.remove());anchors=[];document.querySelector('.site-editor-preview')?.remove();preview=false;}
 function readForm(){overlay.querySelectorAll('[data-editor-field]').forEach(el=>draft.texts[el.dataset.editorField]=el.value.slice(0,1500));}
 function message(text){overlay.querySelector('[role="status"]').textContent=text;}
 function render(){
 overlay?.remove();overlay=document.createElement('section');overlay.className='site-editor';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-label','Editor do site em teste');
 overlay.innerHTML='<div class="site-editor-inner"><h2>Editor do site · teste</h2><p>Rascunho privado neste navegador. Não altera o site dos clientes. Textos simples, sem código ou HTML.</p><div class="site-editor-actions"><button data-editor-save>Salvar rascunho</button><button data-editor-preview>Ver prévia</button><button data-editor-reset>Restaurar original</button><button data-editor-close>Fechar</button></div><p role="status" aria-live="polite"></p><div data-editor-fields></div><h3>Ordem dos blocos principais</h3><p>A abertura e o atendimento permanecem fixos. Use as setas para ordenar coleção, conta e apresentação.</p><div data-editor-order></div></div>';
 const container=overlay.querySelector('[data-editor-fields]');fields.forEach(([id,label])=>{const wrap=document.createElement('label');wrap.textContent=label;const input=document.createElement('textarea');input.dataset.editorField=id;input.maxLength=1500;input.value=draft.texts[id];wrap.append(input);container.append(wrap);});
 draft.order.forEach((id,i)=>{const row=document.createElement('p');row.append(document.createTextNode(blocks.find(b=>b[0]===id)[1]+' '));[-1,1].forEach(delta=>{const b=document.createElement('button');b.textContent=delta<0?'↑ Subir':'↓ Descer';b.disabled=i+delta<0||i+delta>=draft.order.length;b.onclick=()=>{readForm();[draft.order[i],draft.order[i+delta]]=[draft.order[i+delta],draft.order[i]];render();};row.append(b);});overlay.querySelector('[data-editor-order]').append(row);});
 overlay.onclick=async event=>{const b=event.target.closest('button');if(!b)return;try{
 if(b.hasAttribute('data-editor-close')){readForm();overlay.remove();return;}
 if(!['data-editor-save','data-editor-preview','data-editor-reset'].some(a=>b.hasAttribute(a)))return;
 if(await authorized()!==userId)throw Error('A conta mudou. Abra o editor novamente.');readForm();
 if(b.hasAttribute('data-editor-save')){localStorage.setItem('scorsattoSiteDraft:'+userId,JSON.stringify(draft));message('Rascunho salvo somente neste navegador. Nada foi publicado.');}
 if(b.hasAttribute('data-editor-reset')){if(!confirm('Restaurar o rascunho para os textos e posições originais?'))return;draft=structuredClone(baseline);localStorage.removeItem('scorsattoSiteDraft:'+userId);render();}
 if(b.hasAttribute('data-editor-preview')){anchors=blocks.map(([id])=>{const node=getBlock(id),anchor=document.createComment('editor-original-position');node.after(anchor);return[node,anchor];});apply(draft);preview=true;overlay.remove();closeBackofficePage();closeAccount();const bar=document.createElement('div');bar.className='site-editor-preview';bar.innerHTML='<strong>Prévia privada · não publicada</strong><button data-preview-edit>Voltar ao editor</button><button data-preview-end>Sair da prévia</button>';bar.onclick=async e=>{if(!e.target.closest('button'))return;const edit=e.target.hasAttribute('data-preview-edit');restore();if(edit){try{await authorized();render();}catch(err){alert(err.message);}}};document.body.append(bar);window.scrollTo({top:0});}
 }catch(err){message(err.message||'Não foi possível concluir.');}};
 document.body.append(overlay);overlay.querySelector('button').focus();
 }
 if(typeof db!=='undefined'&&db)db.auth.onAuthStateChange((_event,session)=>{if(userId&&session?.user?.id!==userId){restore();overlay?.remove();draft=null;userId=null;}});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(overlay?.isConnected){readForm();overlay.remove();}restore();}});
 document.addEventListener('click',async event=>{if(!event.target.closest('[data-site-editor-open]'))return;try{const id=await authorized();restore();baseline ||= capture();if(userId!==id||!draft){userId=id;try{draft=normalize(JSON.parse(localStorage.getItem('scorsattoSiteDraft:'+id)||'null'));}catch{draft=structuredClone(baseline);}}render();}catch(err){alert(err.message);}});
})();
