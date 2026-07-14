# Integração Instagram SCORSATTO

Esta integração prepara o backoffice para receber leads reais do Instagram via Meta API.

## O que fica pronto

- Tabela `instagram_leads` para armazenar @, origem, contexto e status.
- Edge Function `instagram-webhook` para receber eventos da Meta.
- Backoffice lendo `instagram_leads` quando a tabela existir.

## Passos na Meta

1. Usar uma conta Instagram Business ou Criador.
2. Vincular o Instagram a uma Página do Facebook.
3. Criar um app em Meta for Developers.
4. Adicionar Instagram/Messaging conforme o caso.
5. Configurar Webhooks apontando para:
   `https://SEU-PROJETO.supabase.co/functions/v1/instagram-webhook`
6. Definir o mesmo `META_WEBHOOK_VERIFY_TOKEN` no Supabase e na Meta.
7. Passar por App Review para permissões necessárias antes de usar em produção.

## Variáveis no Supabase

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `META_WEBHOOK_VERIFY_TOKEN`

Nunca coloque token da Meta ou service role key no `index.html`.

## Observação comercial

A API oficial não deve ser usada para disparo frio em massa. Use para captar interações reais: comentários, DMs, respostas de story, cliques de anúncio e indicações autorizadas.
