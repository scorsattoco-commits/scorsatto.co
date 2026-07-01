# SCORSATTO Supabase

Esta pasta prepara o backend real da SCORSATTO.

Onde ver os dados quando conectar:

- Supabase > Authentication > Users: clientes cadastrados e logins.
- Supabase > Table Editor > profiles: nome, telefone, cidade e estado.
- Supabase > Table Editor > favorites: peças favoritas por cliente.
- Supabase > Table Editor > addresses: endereços de entrega.
- Supabase > Table Editor > cart_items: produtos atualmente no carrinho por cliente.
- Supabase > Table Editor > orders: pedidos e histórico.
- Supabase > Table Editor > customer_events: eventos de comportamento.
- Supabase > Table Editor > admin_users: Alisson e Miguel como administradores.
- Supabase > Table Editor > product_overrides: edições feitas pelo painel admin do site.
- Supabase > Views > abandoned_carts: clientes com carrinho parado há mais de 2 horas.
- Supabase > Logs: eventos técnicos.

Para acessos, visualizações e comportamento:

- Google Analytics 4: usuários, sessões, páginas vistas e origem do tráfego.
- Microsoft Clarity: gravações de sessão, mapa de calor e cliques.

Próximo passo:

1. Criar projeto em https://supabase.com.
2. Abrir SQL Editor.
3. Rodar o arquivo schema.sql desta pasta.
4. Copiar `config.example.js` para `config.js`, ou editar o `config.js` existente.
5. Preencher:
   - `window.SCORSATTO_SUPABASE_URL`
   - `window.SCORSATTO_SUPABASE_ANON_KEY`
   - `window.SCORSATTO_ADMIN_EMAILS`
6. Criar os usuários de Alisson e Miguel em Supabase > Authentication > Users.
7. Adicionar os dois usuários na tabela `admin_users`, usando o `id` do Auth em `user_id` e o mesmo e-mail de login.
8. Publicar o site.

Quando `config.js` estiver preenchido, o site usa Supabase Auth para login real e grava perfis, endereços, favoritos, carrinho, pedidos e edições administrativas no banco. Enquanto as chaves estiverem vazias, o site usa um fallback local isolado por sessão para não mostrar carrinho antigo de outro acesso.

Depois do login, a aba `Admin` aparece em Minha conta apenas para os e-mails configurados e cadastrados como administradores.
