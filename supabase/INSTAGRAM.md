# Integracao Instagram SCORSATTO

Esta integracao prepara o backoffice para receber leads reais do Instagram via API oficial da Meta.

## O que fica pronto

- Tabela `instagram_leads` para armazenar arroba, nome, origem, contexto, status e score.
- Edge Function `instagram-webhook` para receber eventos enviados pela Meta.
- Script diario `scripts/sync_instagram_leads.py` para buscar comentarios/conversas e gravar no Supabase.
- Backoffice lendo `instagram_leads` quando a tabela existir.

## Passos na Meta

1. Usar uma conta Instagram Business ou Criador.
2. Vincular o Instagram a uma Pagina do Facebook.
3. Criar ou usar o app da SCORSATTO no Meta for Developers.
4. Adicionar Instagram Platform / Instagram Messaging conforme a permissao liberada.
5. Configurar Webhooks apontando para:
   `https://SEU-PROJETO.supabase.co/functions/v1/instagram-webhook`
6. Definir o mesmo `META_WEBHOOK_VERIFY_TOKEN` no Supabase e na Meta.
7. Configurar as variaveis de ambiente da rotina diaria.
8. Passar por App Review quando a Meta exigir permissoes de producao.

## Variaveis necessarias

Nunca coloque tokens no `index.html`.

Use somente no Supabase, no Windows local ou em ambiente seguro:

- `META_ACCESS_TOKEN`: token oficial da Meta.
- `META_INSTAGRAM_BUSINESS_ID`: ID da conta Instagram Business/Criador.
- `META_PAGE_ID`: ID da Pagina Facebook vinculada.
- `META_WEBHOOK_VERIFY_TOKEN`: token livre definido por voce para validar webhook.
- `SCORSATTO_SUPABASE_URL` ou `SUPABASE_URL`: URL do projeto Supabase.
- `SCORSATTO_SUPABASE_SERVICE_ROLE_KEY` ou `SUPABASE_SERVICE_ROLE_KEY`: service role key para gravar no banco.

## Rotina diaria

`scripts/run_daily_automation.ps1` chama `scripts/sync_instagram_leads.py`.

Com as variaveis configuradas, o script tenta buscar:

- comentarios recentes em midias da conta profissional;
- conversas Instagram vinculadas a Pagina Facebook;
- nome, arroba, origem, contexto, score e ultima interacao.

Sem token da Meta, ele nao inventa leads. Ele grava um relatorio dizendo o que falta em:

`data/automacoes/instagram/instagram-sync-AAAA-MM-DD.json`

## Regra comercial

A API oficial deve ser usada para captar interacoes reais: comentarios, DMs, respostas de story, cliques de anuncio e indicacoes autorizadas.

Nao use isso para disparo frio em massa. O painel deve ajudar a escolher 10 pessoas por dia com contexto real, nao virar spam.
