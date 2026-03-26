# Jtasks — Guia de Instalação

## Visão Geral

**Jtasks** é um gerenciador de tarefas diárias com autenticação por usuário, banco de dados na nuvem e envio de resumo por email.

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Templates | Jinja2 |
| Interatividade | HTMX |
| Banco de dados | Supabase (PostgreSQL) |
| Autenticação | Supabase Auth (server-side session) |
| Email | SMTP via smtplib |
| Scheduler | APScheduler |
| Export | openpyxl (xlsx) |
| Gráficos | Chart.js v4 (CDN) |

---

## Estrutura do Projeto

```
JtasksApp/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── .env                     # Credenciais (não comitar)
├── .env.example
├── supabase-setup.sql       # SQL para criar tabelas no Supabase
├── app/
│   ├── config.py            # Settings via pydantic-settings
│   ├── deps.py              # Dependency: get_current_user
│   ├── scheduler.py         # APScheduler (email diário)
│   ├── routers/             # auth, tasks, projects, presets, performance, notify, export
│   ├── services/            # supabase_client, email_service, notify_config
│   └── templates/           # Jinja2 templates (base, login, pages, partials)
└── static/
    ├── css/app.css
    └── js/charts.js
```

---

## Instalação

### 1. Clonar e instalar dependências

```bash
git clone https://github.com/jcampelo/JtasksApp.git
cd JtasksApp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar Supabase

1. Criar projeto em [supabase.com](https://supabase.com)
2. Executar `supabase-setup.sql` no SQL Editor
3. Em **Authentication → Sign In → Email**: desativar "Confirm email"
4. Criar usuários em **Authentication → Users → Add user**

### 3. Configurar variáveis de ambiente

Copiar `.env.example` para `.env` e preencher:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua-anon-key
SUPABASE_SERVICE_KEY=sua-service-role-key
SECRET_KEY=chave-secreta-aleatoria
```

As chaves ficam em **Settings → API** no painel do Supabase.

### 4. Executar

```bash
python main.py
# Saída: "Jtasks rodando em http://0.0.0.0:8080"
```

Ou com uvicorn diretamente:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Acessar: `http://localhost:8080`

---

## Deploy na VPS (Ubuntu 22.04)

### Serviço systemd

```ini
[Unit]
Description=Jtasks
After=network.target

[Service]
WorkingDirectory=/opt/jtasks
ExecStart=/opt/jtasks/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable jtasks
systemctl start jtasks
```

### Enviar arquivos

```bash
scp -P 22022 -r app/ static/ main.py requirements.txt .env root@SEU_IP:/opt/jtasks/
ssh -p 22022 root@SEU_IP "systemctl restart jtasks"
```

---

## Configuração de Email

Acessar aba **📧 Notificações** na aplicação e preencher:

| Campo | Exemplo (Gmail) |
|-------|----------------|
| Destinatário | seu@email.com |
| Servidor SMTP | smtp.gmail.com |
| Porta | 587 |
| Usuário | conta@gmail.com |
| Senha | App Password (16 chars) |
| Horário | 08:00 |

**Gmail:** criar App Password em `myaccount.google.com → Segurança → Senhas de app`
