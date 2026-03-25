# Jabil Notes — Guia Completo de Instalação do Zero

## Visão Geral da Aplicação

**Jabil Notes** é um rastreador de atividades diárias com autenticação por usuário, banco de dados na nuvem e envio de resumo por email. Cada usuário tem dados completamente separados dos demais.

---

## Stack Tecnológica

| Camada | Tecnologia | Detalhe |
|--------|-----------|---------|
| Frontend | HTML + CSS + JS puro | Arquivo único (`index.html`) |
| Banco de dados | Supabase (PostgreSQL) | Plano free ou pago |
| Autenticação | Supabase Auth | Email + senha |
| Backend | Python 3 (stdlib pura) | `http.server`, sem frameworks |
| Email | SMTP via `smtplib` | Gmail, Office 365 ou qualquer SMTP |
| Exportação | SheetJS (XLSX) | CDN `xlsx.full.min.js` |
| Gráficos | Chart.js v4 | CDN |
| Hospedagem | VPS Ubuntu 22.04 | Porta 8080, systemd |

---

## Arquivos da Aplicação

```
jabil-tasks/
├── index.html          # Frontend completo (HTML + CSS + JS)
├── server.py           # Backend Python (HTTP server + email scheduler)
├── supabase-setup.sql  # SQL para criar tabelas e RLS no Supabase
└── config.json         # Criado automaticamente ao salvar config de email
```

---

## Parte 1 — Supabase (Banco de Dados + Auth)

### 1.1 Criar Projeto no Supabase

1. Acessar [supabase.com](https://supabase.com) → **New Project**
2. Escolher nome, senha do banco e região (preferencialmente São Paulo)
3. Aguardar provisionamento (~2 min)

### 1.2 Anotar Credenciais

Ir em **Settings → API** e copiar:

| Credencial | Onde usar | Nível de segurança |
|-----------|-----------|-------------------|
| **Project URL** | `index.html` + `server.py` | Pública |
| **anon / public key** | `index.html` apenas | Pública (segura no frontend) |
| **service_role / secret key** | `server.py` apenas | **NUNCA expor no frontend** |

### 1.3 Criar as Tabelas (SQL Editor)

No painel Supabase → **SQL Editor → New query** → colar e executar o conteúdo de `supabase-setup.sql`.

### 1.4 Configurar Autenticação

No painel Supabase → **Authentication → Sign In / Providers → Email**:
- ✅ **Enable Email provider** — ATIVAR
- ☐ **Confirm email** — DESATIVAR (permite login imediato sem confirmar email)

### 1.5 Criar Usuários

No painel Supabase → **Authentication → Users → Add user → Create new user**:
- Preencher email e senha
- ✅ Marcar **"Auto Confirm User"**
- Clicar **Create user**

> O gerenciamento de usuários é feito exclusivamente pelo painel do Supabase. Não há interface de cadastro na aplicação.

---

## Parte 2 — index.html (Frontend)

### 2.1 Inserir Credenciais Supabase

Abrir `index.html` e localizar as linhas (~950):

```javascript
const SUPABASE_URL = "https://SEU_PROJETO.supabase.co";   // ← substituir
const SUPABASE_ANON_KEY = "sua-anon-key-aqui";            // ← substituir
```

### 2.2 Dependências CDN (já inclusas no arquivo)

```html
<script src="https://cdn.jsdelivr.net/npm/xlsx/dist/xlsx.full.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
```

### 2.3 Funcionalidades

| Aba | Função |
|-----|--------|
| 📋 Ativas | Adicionar e gerenciar tarefas ativas (agrupadas por prioridade) |
| ✅ Concluídas | Ver e exportar tarefas concluídas |
| 📁 Projetos | Criar e remover projetos |
| 📊 Performance | Gráficos de desempenho |
| 📧 Notificações | Configurar envio de email diário |

**Por tarefa:** 💬 Atualizações · ✏️ Editar · 🗑️ Descartar · ✓ Concluir

**Exportação Excel:** Nome, Projeto, Prioridade, Status, Deadline, Criada em, Concluída em, Atualizações

**Temas:** dark/light via 🌙/☀️ no header — preferência salva no `localStorage`

---

## Parte 3 — server.py (Backend Python)

### 3.1 Inserir Credenciais Supabase

Abrir `server.py` e localizar as constantes (~linha 14):

```python
SUPABASE_URL = "https://SEU_PROJETO.supabase.co"   # ← substituir
SUPABASE_SERVICE_KEY = "sua-service-role-key"       # ← substituir
```

### 3.2 Rotas HTTP

| Método | Rota | Função |
|--------|------|--------|
| GET | `/` ou `/index.html` | Serve o arquivo `index.html` |
| GET | `/config` | Retorna configurações de email (sem expor a senha) |
| POST | `/config` | Salva configurações de email em `config.json` |
| POST | `/notify/send` | Dispara email imediatamente |

### 3.3 Scheduler de Email

- Roda em background (daemon thread)
- Verifica a cada **30 segundos** se é hora de enviar
- Lê `config.json` dinamicamente (mudanças de horário não requerem restart)
- Busca tarefas do Supabase via REST API com a `service_role` key

### 3.4 Executar o Servidor

```bash
python3 server.py
# Saída: "Jabil Notes rodando em http://0.0.0.0:8080"
```

---

## Parte 4 — Deploy na VPS (Hostgator Ubuntu 22.04)

### 4.1 Informações do Servidor

| Item | Valor |
|------|-------|
| Porta SSH | `22022` (não padrão) |
| Porta da aplicação | `8080` |
| Pasta da aplicação | `/opt/jabil-notes/` |
| Serviço systemd | `jabil-notes` |
| OS | Ubuntu 22.04 LTS |

### 4.2 Primeira Instalação na VPS

```bash
# 1. Conectar
ssh -p 22022 root@SEU_IP

# 2. Criar pasta
mkdir -p /opt/jabil-notes

# 3. Criar serviço systemd
nano /etc/systemd/system/jabil-notes.service
```

Conteúdo do serviço:
```ini
[Unit]
Description=Jabil Notes
After=network.target

[Service]
WorkingDirectory=/opt/jabil-notes
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 4. Ativar e iniciar
systemctl daemon-reload
systemctl enable jabil-notes
systemctl start jabil-notes
```

### 4.3 Enviar Arquivos para a VPS

> ⚠️ Rodar no terminal do **Windows PC** (não dentro do SSH)

```bash
scp -P 22022 index.html root@SEU_IP:/opt/jabil-notes/index.html
scp -P 22022 server.py  root@SEU_IP:/opt/jabil-notes/server.py
```

### 4.4 Atualizar Após Mudanças

```bash
# Copiar arquivo atualizado
scp -P 22022 index.html root@SEU_IP:/opt/jabil-notes/index.html

# Reiniciar serviço
ssh -p 22022 root@SEU_IP "systemctl restart jabil-notes"
```

### 4.5 Verificar Status

```bash
ssh -p 22022 root@SEU_IP "systemctl status jabil-notes"
```

---

## Parte 5 — Configuração de Email (SMTP)

Acessar a aba **📧 Notificações** na aplicação:

| Campo | Exemplo (Gmail) | Exemplo (Office 365) |
|-------|----------------|---------------------|
| Destinatário | seu@email.com | seu@email.com |
| Servidor SMTP | smtp.gmail.com | smtp.office365.com |
| Porta | 587 | 587 |
| Usuário | conta@gmail.com | conta@empresa.com |
| Senha | App Password (16 chars) | Senha da conta |
| Horário | 08:00 | 08:00 |
| Envio automático | ✅ Ativar | ✅ Ativar |

**Para Gmail:** criar App Password em `myaccount.google.com → Segurança → Senhas de app`
(requer autenticação de 2 fatores ativa)

---

## Diagrama de Fluxo

```
Navegador (index.html)
    │
    ├── Login → Supabase Auth (JWT)
    │
    ├── CRUD de tarefas/projetos/presets → Supabase PostgreSQL (RLS por usuário)
    │
    └── Config de email → server.py (/config)
                              │
                              ├── Serve index.html (GET /)
                              ├── Salva config.json (POST /config)
                              └── Scheduler (30s loop)
                                      │
                                      └── Supabase REST API (service_role)
                                              → Busca tarefas ativas
                                              → Envia email SMTP
```

---

## Checklist Completo de Nova Instalação

### Supabase
- [ ] Criar projeto no Supabase
- [ ] Executar `supabase-setup.sql` no SQL Editor
- [ ] Ativar Email provider em Authentication
- [ ] Desativar "Confirm email"
- [ ] Criar primeiro usuário (admin) com "Auto Confirm User"
- [ ] Copiar Project URL, anon key e service_role key

### index.html
- [ ] Inserir `SUPABASE_URL` (linha ~950)
- [ ] Inserir `SUPABASE_ANON_KEY` (linha ~951)

### server.py
- [ ] Inserir `SUPABASE_URL` (linha ~14)
- [ ] Inserir `SUPABASE_SERVICE_KEY` (linha ~15)

### VPS
- [ ] Criar pasta `/opt/jabil-notes/`
- [ ] Copiar `index.html` e `server.py` via SCP
- [ ] Criar e ativar serviço systemd `jabil-notes`
- [ ] Verificar que porta 8080 está acessível
- [ ] Acessar `http://IP:8080` e fazer login

### Email
- [ ] Acessar aba Notificações na aplicação
- [ ] Preencher dados SMTP e salvar
- [ ] Testar com "Enviar agora"
- [ ] Ativar envio automático com horário desejado
