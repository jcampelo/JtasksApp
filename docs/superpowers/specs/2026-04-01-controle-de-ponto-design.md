# Controle de Ponto — Design Document

**Data:** 2026-04-01
**Status:** Aprovado pelo usuário

---

## 1. Visão Geral

Funcionalidade de controle de ponto integrada ao JtasksApp. Permite que cada usuário registre entrada e saída diária, visualize horários calculados automaticamente, acompanhe histórico mensal e acumule banco de horas e horas extras.

Acesso via botão dedicado no sidebar do app. O botão navega para `/timeclock`, que é uma página standalone (estende `base.html`) fora do shell de tabs. A página inclui o sidebar para navegação de volta ao app principal. O endpoint GET `/timeclock` retorna a página completa em requests normais; em requests HTMX (header `HX-Request`), retorna apenas o conteúdo parcial.

---

## 2. Regras de Negócio

### Jornada

| Parâmetro | Valor |
|-----------|-------|
| Jornada normal | 8h48min |
| Jornada máxima | 9h30min |
| Intervalo almoço | 1h (fixo) |
| Entrada | Flexível (horário registrado pelo usuário) |

### Cálculo de Saída

A partir do horário de entrada:
- **Saída normal** = entrada + 8h48 + 1h (almoço) = entrada + 9h48
- **Saída máxima** = entrada + 9h30 + 1h (almoço) = entrada + 10h30

Exemplo: entrada 06:06 → saída normal 15:54, saída máxima 16:36.

### Classificação de Horas

| Dia | Tempo extra | Classificação |
|-----|-------------|---------------|
| Segunda a Sexta | Além de 8h48 | **Banco de horas** (acumula) |
| Sábado e Domingo | Todo o tempo trabalhado | **Hora extra** |

### Saldo Diário (dias de semana)

- Saída real > saída normal → saldo positivo (banco de horas)
- Saída real < saída normal → saldo negativo (atraso/débito)
- Saída real = saída normal → saldo zero
- Tempo extra não pode exceder 42min (limite de 9h30 - 8h48)

### Fins de Semana

- Não há saída normal nem máxima
- Horas trabalhadas = saída real - entrada (sem desconto de almoço — fins de semana não têm intervalo obrigatório)
- Todo o tempo é contabilizado como hora extra

---

## 3. Componentes da Página

### 3.1 Registro de Ponto (topo da página)

**3 estados:**

**Estado 1 — Sem registro hoje:**
- Exibe data atual e mensagem "Nenhum registro hoje"
- Botão "Registrar Entrada" (usa horário atual do clique)

**Estado 2 — Entrada registrada:**
- Exibe 3 horários lado a lado: Entrada, Saída Normal, Saída Máxima
- Saída Normal mostra "8h48 trabalhadas" abaixo
- Saída Máxima mostra "9h30 trabalhadas" abaixo
- Botão "Registrar Saída" (usa horário atual do clique)

**Estado 3 — Dia completo:**
- Exibe 4 horários: Entrada, Saída Normal, Saída Máxima, Saída Real
- Saldo do dia calculado abaixo da saída real (ex: "+16min banco de horas")

### 3.2 Tabela Mensal

**Navegação:** setas ◀ ▶ para alternar entre meses.

**Colunas:**

| Coluna | Descrição |
|--------|-----------|
| Data | DD/MM |
| Dia | Seg, Ter, ... Dom |
| Entrada | Horário registrado (verde) |
| Saída Normal | Calculada (azul) — "—" nos fins de semana |
| Saída Máxima | Calculada (laranja) — "—" nos fins de semana |
| Saída Real | Horário registrado |
| Trabalhadas | Total de horas efetivas |
| Saldo | +Xmin banco / +Xh extra / -Xmin atraso |

**Cores do saldo:**
- Azul (#4fc3f7): banco de horas (dia de semana, positivo)
- Laranja (#ffa726): hora extra (fim de semana)
- Vermelho (#e74c3c): atraso/débito (saiu antes do normal)
- Cinza (#888): saldo zero

**Ordenação:** mais recente no topo.

### 3.3 Resumo/Totalizadores

6 cards em grid 3×2:

| Card | Descrição |
|------|-----------|
| Dias Trabalhados | X / Y (trabalhados / dias úteis do mês) |
| Horas Trabalhadas | Total do mês |
| Média Diária | Horas trabalhadas / dias trabalhados |
| Banco de Horas | Saldo acumulado **global** — soma de todos os registros, não apenas do mês (azul, positivo/negativo) |
| Horas Extras | Total de horas em fins de semana (laranja) |
| Atrasos | Total de débitos por saída antecipada (vermelho) |

### 3.4 Ajuste Manual

- Cada linha da tabela tem um botão de edição (ícone lápis) que abre o modal de ajuste
- Modal permite editar entrada e saída real do registro selecionado
- Para corrigir divergências no banco de horas ou registros incorretos
- Registra que houve ajuste (campo `adjusted: true` no registro)

---

## 4. Banco de Dados

### Nova tabela: `time_records`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | uuid (PK) | ID do registro |
| user_id | uuid (FK) | Referência ao usuário |
| date | date (unique por user) | Data do registro |
| clock_in | timestamptz | Horário de entrada |
| clock_out | timestamptz | Horário de saída real (null se ainda não saiu) |
| expected_out | time | Saída normal calculada |
| max_out | time | Saída máxima calculada |
| worked_minutes | integer | Horas efetivas trabalhadas (em minutos, para simplificar cálculos Python) |
| balance_minutes | integer | Saldo em minutos (+positivo, -negativo). Derivado: dia de semana positivo = banco, dia de semana negativo = atraso, fim de semana = hora extra |
| is_weekend | boolean | Se é sábado ou domingo |
| adjusted | boolean | Se foi editado manualmente (default false) |
| created_at | timestamptz | Timestamp de criação |

**Constraints:**
- `unique(user_id, date)` — um registro por dia por usuário
- RLS habilitado com policy filtrando por `user_id`

---

## 5. API (Endpoints)

### Router: `app/routers/timeclock.py`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/timeclock` | Página principal (HTML) |
| POST | `/timeclock/clock-in` | Registrar entrada |
| POST | `/timeclock/clock-out` | Registrar saída |
| GET | `/timeclock/records?month=YYYY-MM` | Tabela mensal (partial HTMX) |
| GET | `/timeclock/summary?month=YYYY-MM` | Totalizadores (partial HTMX) |
| PUT | `/timeclock/records/{id}` | Ajuste manual de registro |

Todos os endpoints seguem o padrão obrigatório:
- `user=Depends(get_current_user)`
- `get_user_client(user["access_token"], user["refresh_token"])`
- `.eq("user_id", user["user_id"])` em toda query

---

## 6. Templates

### Novos arquivos:

| Arquivo | Descrição |
|--------|-----------|
| `templates/pages/timeclock.html` | Página principal (estende base.html) |
| `templates/partials/timeclock/clock_status.html` | Estado do registro do dia (3 estados) |
| `templates/partials/timeclock/records_table.html` | Tabela mensal |
| `templates/partials/timeclock/summary.html` | Cards totalizadores |
| `templates/partials/timeclock/adjust_modal.html` | Modal de ajuste manual |

### Interações HTMX:

- Botão entrada/saída → POST → retorna `clock_status.html` atualizado
- Navegação mês → GET com query param → retorna `records_table.html` + `summary.html`
- Ajuste manual → modal carregado via HTMX → PUT → refresh tabela e resumo

---

## 7. Sidebar

Adicionar botão "Controle de Ponto" no `templates/partials/sidebar.html` com ícone de relógio. Link `<a href="/timeclock">` que navega para a página standalone. A página `/timeclock` inclui o sidebar para que o usuário possa voltar ao app principal (`/app`).

---

## 8. Decisões de Design

1. **Valores fixos de jornada** — 8h48 normal, 9h30 máxima, 1h almoço. Não configurável por usuário.
2. **Registro por clique** — usa horário do servidor no momento do clique, sem input manual (exceto ajuste).
3. **Página standalone** — estende `base.html`, inclui sidebar, acessada via link no sidebar. Não faz parte do shell de tabs.
4. **Banco de horas acumulativo** — saldo total = `SUM(balance_minutes) WHERE is_weekend=false` sobre todos os registros do usuário. Não há "data de início" — soma desde o primeiro registro. Ajuste manual disponível para correções.
5. **Fim de semana sem jornada base** — todo tempo trabalhado é hora extra. Sem desconto de almoço.
6. **CSS cache-busting** — o endpoint GET `/timeclock` deve passar `css_version` no contexto do template, seguindo o padrão de `app_router.py`.
7. **`worked_minutes` como inteiro** — armazenar minutos em vez de interval para simplificar cálculos no Python e evitar parsing de strings do Supabase.
