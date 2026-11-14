# Importação aditiva do catálogo em equipe

Preparação da parte de destino. Não é uma integração completa e não contém agendamento. Não altera o site até execução explícita com `--apply`; o comando apenas prepara arquivos locais, não faz deploy nem atualiza a etapa da central.

## Dependências ainda pendentes

- Obter o código real da central hospedada em scorsatto-intelligence.alissonscorsatto.chatgpt.site/workflow/ e seu mecanismo de persistência. O repositório scorsattoco-commits/scorsatto acessível em 13/11/2026 contém apenas um CRM local (app.js, index.html, styles.css, README.md), sem o fluxo de peças.
- Criar a etapa persistente No site como última aba na central, com atualização somente após confirmação pública da publicação.
- Implementar exportação autenticada de Prontas para o site para o contrato abaixo e copiar somente as imagens editadas com vínculo de referência e hash.
- Consultar também produtos manuais e overrides administrativos persistidos antes de importar; o importador atual confere o catálogo estático, não pode garantir sozinho a ausência de referências criadas no backend.
- Validar o resultado público e concluir o retorno por referência na central. O relatório mantém publicationVerified=false até existir essa verificação externa.

## Uso sob demanda

`node --test scripts/test-import-team-ready.mjs`

`node scripts/import-team-ready.mjs caminho/manifesto.json` prepara somente o relatório.

`node scripts/import-team-ready.mjs caminho/manifesto.json --apply` acrescenta produtos e cores ao index.html e salva backup em .local-data. Fazer isso somente depois das verificações de backend acima. Em seguida executar o gerador existente de catalogo.json, revisar a alteração, publicar pelo fluxo GitHub Pages e conferir os URLs públicos. Não executar o publicador histórico publish_ready_products.mjs, que usa outra fila e substitui registros.

## Contrato de exportação a implementar na origem

Objeto version=1, source="scorsatto-team-workflow", groups=[...]. Cada grupo precisa de:

- id estável da central; identityConfirmed=true; brand; name do modelo sem a cor; category exata já existente na loja.
- price numérico de venda comprovado e priceEvidence indicando a fonte da regra/valor. Não copiar preço por semelhança.
- targetSiteGroupId opcional, apenas depois de conferir a identidade de um grupo existente. Se o grupo já contiver referências publicadas, o vínculo pode ser identificado pelas mesmas referências. Não agrupar apenas pelo nome.
- variants: reference numérica do catálogo; supplierCode separado, quando disponível; stage="ready"; color; sizes comprovados; description comprovada; supplierUrl quando disponível; composition e care somente se informados.
- image por variante: kind="edited", reference igual à referência da variante, path em generated/catalogo-equipe/*.png e sha256 do arquivo copiado da foto editada. O arquivo precisa ser PNG 1100x1100. A proveniência requer exportação autenticada; o hash sozinho não prova que uma foto foi gerada.

O importador preserva produtos existentes integralmente; em grupos parcialmente existentes acrescenta apenas novas cores e mantém slug canônico, metadados e ordem das cores antigas. Referências já existentes são reportadas sem substituição de imagem. Dados faltantes deixam o grupo inteiro pendente. O estoque físico não é inferido dos tamanhos do fornecedor e os novos produtos são sob consulta.

O publicador não verifica sozinho fidelidade de etiqueta ou conteúdo visual. As fotos devem ter sido revisadas antes da etapa pronta. Nunca usar a fotografia original do fornecedor como fallback.

## Retomada e idempotência

Após deploy interrompido, comparar novamente todas as referências no destino, incluindo backend. Uma publicação já existente deve concluir apenas o retorno No site. Nunca marcar a etapa com base apenas no relatório local. Preservar alterações concorrentes e conferir o estado atual antes do commit/deploy.

