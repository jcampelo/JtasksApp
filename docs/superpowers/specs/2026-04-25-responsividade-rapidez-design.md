# Responsividade e Rapidez nas Acoes de Tarefas - Design Spec

**Data:** 2026-04-25  
**Projeto:** JtasksApp  
**Status:** Design documentado para retomada futura; implementacao pausada  
**Escopo:** Melhorar velocidade percebida e responsividade, com foco em acoes de tarefas e filtros

---

## Contexto

O JtasksApp ja usa FastAPI, Jinja2, HTMX, Alpine.js e Supabase. A tela principal carrega as abas sob demanda e a lista de tarefas ativas fica em `#panel-ativas`.

Pelos fluxos revisados, os pontos com maior potencial de ganho sao:

1. Acoes de tarefas, como criar, editar, concluir, duplicar, alterar prioridade, checklist e updates.
2. Filtros e busca da lista de tarefas.
3. Evitar recarregamentos grandes do painel quando apenas a lista ou uma parte dela precisa mudar.
4. Preservar o contexto do usuario, principalmente filtros ativos, estado visual e modal aberto/fechado.

O usuario escolheu um pacote geral, equilibrado entre celular e desktop, com mudancas visuais moderadas. Backend pode ser alterado somente quando isso trouxer ganho claro.

---

## Objetivo

Deixar o uso diario mais rapido sem redesenhar a aplicacao inteira.

O foco e reduzir a sensacao de peso em operacoes frequentes:

- Filtrar e buscar tarefas.
- Criar nova tarefa.
- Editar tarefa.
- Concluir tarefa.
- Duplicar tarefa.
- Alterar prioridade.
- Adicionar notas, updates e checklist.

---

## Nao Objetivos

Esta especificacao nao inclui:

- Redesenho completo da interface.
- Novo framework frontend.
- WebSocket, SSE ou realtime Supabase.
- Mudanca de banco ou nova tabela.
- Paginacao completa da lista de tarefas.
- Reorganizacao ampla das abas do sistema.

Esses itens podem ser discutidos depois, se a lista crescer muito ou se os ganhos iniciais nao forem suficientes.

---

## Alternativas Consideradas

### A. Ganho rapido e seguro

Atualizar apenas os alvos necessarios via HTMX, preservar filtros e melhorar feedback visual de carregamento.

**Vantagens:** baixo risco, pouco backend, entrega rapida.  
**Desvantagens:** nao resolve todos os casos de payload pesado se o usuario tiver muitas tarefas.

### B. Fluxo de tarefas mais fluido

Inclui a alternativa A e reorganiza partes da UI, como filtros, botoes de acao e comportamento mobile.

**Vantagens:** melhora ergonomia alem da velocidade percebida.  
**Desvantagens:** exige mais validacao visual e aumenta o trabalho neste momento.

### C. Otimizacao profunda

Inclui A/B e revisa consultas Supabase, payloads, joins e carregamento sob demanda de dados auxiliares.

**Vantagens:** maior ganho potencial em contas com muitas tarefas.  
**Desvantagens:** maior risco e mais testes, pois toca mais backend.

### Decisao

Seguir com **A + parte seletiva de C**:

- Primeiro reduzir refreshes grandes e preservar filtros.
- Depois otimizar consultas/payloads apenas onde houver ganho claro.
- Manter alteracoes visuais moderadas e localizadas.

---

## Arquitetura Proposta

A lista de tarefas passa a ter um fluxo de atualizacao centralizado:

1. O estado atual dos filtros fica disponivel em um controlador frontend unico.
2. Acoes de tarefa disparam eventos HTMX claros, como `refreshTasks`, `closeModal` e `showToast`.
3. O refresh de tarefas usa sempre os filtros atuais.
4. O alvo padrao passa a ser `#task-list-body`, nao o painel inteiro `#panel-ativas`.
5. O backend retorna fragmentos menores sempre que possivel.

Essa abordagem evita reconstruir formulario, filtros e painel inteiro quando so a lista precisa mudar.

---

## Componentes

### 1. Controlador da lista de tarefas

Local provavel: script em `app/templates/partials/tasks/task_list.html`, possivelmente migrado depois para arquivo JS em `static/js/`.

Responsabilidades:

- Manter `search`, `project`, `priority`, `sort` e `overdue`.
- Montar `URLSearchParams` dos filtros atuais.
- Expor uma funcao global pequena, por exemplo `window.jtasksTasks.refresh()`.
- Evitar requisicoes concorrentes de filtro, escolhendo na implementacao entre debounce, cancelamento da chamada anterior ou `hx-sync`.
- Restaurar estados de loading se a requisicao falhar.

### 2. Endpoint de corpo da lista

Endpoint existente: `GET /tasks/filter`.

Responsabilidades:

- Receber filtros atuais.
- Buscar somente tarefas ativas do usuario logado.
- Renderizar `partials/tasks/task_list_body.html`.
- Continuar filtrando todas as queries por `user_id`.

### 3. Eventos HTMX de acao

Acoes como criar, editar, duplicar, concluir, prioridade, checklist e updates devem preferir:

- `HX-Trigger: {"showToast": "...", "refreshTasks": true}`
- `HX-Trigger: {"closeModal": true, "refreshTasks": true, "showToast": "..."}`

O frontend decide como atualizar a lista preservando filtros. O backend nao precisa saber o estado visual do navegador, exceto quando a propria rota ja recebe filtros.

### 4. Modais

Modais continuam sendo carregados em `#modal-container`.

Ao salvar com sucesso:

- O modal fecha via evento `closeModal`.
- A lista atualiza via `refreshTasks`.
- O toast confirma a acao.

Se houver erro:

- O modal permanece aberto.
- O erro aparece no proprio modal ou em toast de erro.
- Os campos preenchidos nao devem ser descartados.

---

## Fluxos

### Filtros e Busca

1. Usuario altera busca, projeto, prioridade, atrasadas ou ordenacao.
2. Controlador monta query string atual.
3. HTMX chama `/tasks/filter?...`.
4. Apenas `#task-list-body` e substituido.
5. Formulario de nova tarefa e toolbar de filtros permanecem intactos.

### Criar Tarefa

1. Usuario envia o formulario.
2. Backend cria a tarefa com `user_id`.
3. Backend dispara `showToast` e `refreshTasks`.
4. Frontend limpa o formulario se a criacao foi bem-sucedida.
5. Lista e recarregada com filtros atuais.

Se a nova tarefa nao combinar com os filtros ativos, ela pode nao aparecer imediatamente. Isso e correto, desde que o toast confirme a criacao.

### Editar Tarefa

1. Usuario abre o modal de edicao.
2. Backend carrega a tarefa filtrando por `id` e `user_id`.
3. Ao salvar, backend atualiza somente a tarefa do usuario.
4. Backend dispara `closeModal`, `showToast` e `refreshTasks`.
5. Lista atual e recarregada com filtros preservados.

Se a edicao mudar projeto, prioridade ou prazo, a tarefa pode sair da lista filtrada. Isso tambem e correto.

### Duplicar Tarefa

1. Usuario aciona duplicacao a partir do modal de edicao.
2. Backend busca a tarefa original filtrando por `id` e `user_id`.
3. Backend cria a copia com o mesmo `user_id` autenticado.
4. A allowlist de campos copiados e fechada: `name`, `project`, `priority` e `deadline`.
5. A copia sempre recebe `status="active"` e `date=date.today().isoformat()`.
6. A copia nunca herda `id`, `created_at`, `completed_at`, `task_updates`, `task_checklist`, status anterior ou metadados de auditoria.
7. Backend dispara `closeModal`, `showToast` e `refreshTasks`.
8. Lista atual e recarregada com filtros preservados.

Se a tarefa duplicada nao combinar com os filtros ativos, ela pode nao aparecer imediatamente. Isso e correto, desde que o toast confirme a duplicacao.

### Concluir ou Descartar

1. Usuario confirma a acao.
2. Backend altera `status` da tarefa filtrando por `id` e `user_id`.
3. Lista ativa e recarregada pelo corpo da lista.
4. Contadores de grupos por prioridade ficam consistentes.

Apesar de ser possivel remover apenas a linha, o refresh de `#task-list-body` e mais seguro porque os cabecalhos de grupo mostram contagens.

### Prioridade

1. Usuario altera prioridade.
2. Backend atualiza a tarefa filtrando por `id` e `user_id`.
3. Lista ativa e recarregada com filtros atuais.

Isso evita inconsistencias quando a lista esta agrupada por prioridade.

### Checklist, Updates e Notas

1. Acoes internas ao modal atualizam o trecho do modal quando necessario.
2. Contadores visiveis na lista sao atualizados via `refreshTasks`.
3. O modal nao deve fechar automaticamente em acoes pequenas, como adicionar item de checklist ou nota.

---

## Otimizacao Seletiva de Backend

Hoje os helpers de lista usam selecoes como:

```python
.select("*, task_updates(*), task_checklist(*)")
```

Para a lista ativa e filtros, o template precisa principalmente de:

- Dados basicos da tarefa.
- Quantidade de updates.
- Total de checklist.
- Quantidade de itens concluida.

Quando a implementacao for retomada, avaliar trocar a consulta da lista por um payload mais leve, por exemplo selecionando apenas campos necessarios e dados minimos das relacoes:

```python
id, user_id, name, project, priority, status, deadline, created_at, completed_at,
task_updates(id),
task_checklist(id, done)
```

Dados completos de updates/checklist continuam sendo carregados nos modais especificos.

Essa mudanca deve ser feita somente se os refreshes menores ainda nao forem suficientes ou se o payload da lista estiver grande.

---

## Responsividade Visual

Mudancas visuais devem ser moderadas e localizadas:

- Melhorar estados de loading em filtros e botoes de acao.
- Garantir que botoes de tarefa nao quebrem layout no mobile.
- Manter filtros utilizaveis em telas pequenas.
- Evitar que polling ou refresh automatico mexa na tela enquanto o usuario digita.
- Preservar o design system atual: JEMS, navy e teal.

Nao ha necessidade de nova navegacao mobile nesta fase.

---

## Polling e Atualizacao Automatica

O polling atual deve ser ajustado para nao desfazer o contexto do usuario.

Regras propostas:

1. Se o usuario estiver digitando ou com modal aberto, nao atualizar.
2. Se a aba ativa for tarefas, usar os filtros atuais.
3. Evitar chamada sem parametros que resete a lista filtrada.
4. Considerar aumentar o intervalo de 10s para 30s se ainda houver sensacao de peso.
5. Nao atualizar abas que nao ganham valor com polling frequente.

---

## Tratamento de Erros

### Erro ao filtrar

- Manter lista atual visivel.
- Remover estado de loading.
- Mostrar toast de erro.

### Erro ao criar tarefa

- Nao limpar formulario.
- Mostrar mensagem de erro.
- Nao atualizar a lista.

### Erro ao editar/concluir

- Manter modal aberto se houver formulario/modal.
- Mostrar erro no modal ou toast.
- Nao disparar `refreshTasks` em caso de falha.

### Erro em refresh apos acao bem-sucedida

- Mostrar toast informando que a acao foi salva, mas a lista nao atualizou.
- Permitir refresh manual trocando de aba ou usando filtros.

---

## Testes

### Automatizados

Adicionar testes focados em comportamento e seguranca:

- Queries do backend continuam filtrando pelo `user_id` autenticado; o cliente nunca envia nem controla `user_id`.
- `/tasks/filter` preserva filtros recebidos e renderiza somente o corpo da lista.
- Criar, editar, duplicar, concluir e descartar disparam eventos HTMX esperados.
- Nenhum endpoint tocado por este trabalho usa `get_service_client()` para operacoes de usuario.
- Erros de backend nao disparam `refreshTasks` indevidamente.

### Manuais

Validar em desktop e mobile:

- Buscar tarefa e editar uma tarefa filtrada.
- Buscar tarefa e concluir uma tarefa filtrada.
- Duplicar tarefa com filtros ativos e verificar que filtros nao resetam.
- Alterar prioridade com lista agrupada por prioridade.
- Criar tarefa com filtros ativos.
- Adicionar checklist/update e verificar contador na lista.
- Abrir modal e confirmar que polling nao interfere.
- Testar em largura aproximada de 375px, 768px e desktop.

### Verificacao de performance percebida

Usar Chrome DevTools Network para comparar:

- Tamanho das respostas antes/depois.
- Quantidade de requisicoes por acao.
- Tempo de resposta de `/tasks/filter`.
- Se a tela deixa de reconstruir formulario e toolbar a cada acao.

---

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|-----------|
| Eventos frontend ficarem espalhados | Centralizar refresh da lista em uma funcao unica |
| Contadores de prioridade ficarem errados | Atualizar `#task-list-body`, nao apenas a linha, em acoes que mudam grupo/status |
| Filtros serem perdidos apos acao | Toda chamada `refreshTasks` deve usar o estado atual do controlador |
| Modal fechar em caso de erro | Fechar modal somente em resposta de sucesso |
| Backend retornar payload ainda pesado | Aplicar consulta leve seletiva para lista, mantendo dados completos sob demanda |
| Regressao de isolamento por usuario | Testes e revisao obrigatoria de `.eq("user_id", user["user_id"])` |

---

## Criterios de Sucesso

O trabalho pode ser considerado bem-sucedido quando:

1. Filtros e busca nao resetam depois de editar, concluir, duplicar ou alterar prioridade.
2. Acoes comuns atualizam apenas a lista ou modal necessario, nao o painel inteiro.
3. O usuario recebe feedback imediato de loading/sucesso/erro.
4. O fluxo funciona em desktop e celular sem quebra visual relevante.
5. Queries continuam isoladas por `user_id`.
6. Nao ha aumento relevante de complexidade visual ou tecnica.

---

## Proximo Passo Quando Retomar

Quando o trabalho for retomado, criar um plano de implementacao dividido em etapas pequenas:

1. Centralizar refresh da lista e preservacao dos filtros.
2. Migrar acoes principais para eventos HTMX menores.
3. Ajustar polling para respeitar filtros e estado de digitacao/modal.
4. Melhorar loading/erro nos fluxos principais.
5. Medir payload e, se necessario, aplicar consulta leve para a lista.
6. Rodar testes automatizados e validacao manual mobile/desktop.

Nenhuma implementacao foi iniciada nesta etapa.
