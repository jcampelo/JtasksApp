# VPS Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ativar firewall ufw, restringir SSH ao IP fixo do usuário + porta 2222 para CI/CD, e desabilitar CUPS na VPS Hostinger.

**Architecture:** Estratégia híbrida de SSH — porta 22 restrita ao IP fixo do usuário, porta 2222 aberta para o mundo (usada pelo GitHub Actions). ufw como firewall local com política deny-by-default. CUPS desabilitado por não ter uso em servidor.

**Tech Stack:** ufw, sshd, systemd, GitHub Actions (appleboy/ssh-action)

> ⚠️ **ATENÇÃO:** Executar os passos na ordem exata. Desviar da ordem pode resultar em perda de acesso SSH ao servidor. Antes de começar, tenha o **Console Web da Hostinger** aberto como acesso de emergência.

---

### Task 1: Abrir porta 2222 no sshd

**Contexto:** Antes de ativar qualquer firewall, garantir que a porta 2222 está funcional no SSH. Só então restringir a porta 22.

**Arquivos:**
- Modificar: `/etc/ssh/sshd_config` (na VPS via SSH)

- [ ] **Step 1: Conectar na VPS via SSH**

```bash
ssh root@<IP_DA_VPS>
```

- [ ] **Step 2: Fazer backup do sshd_config**

```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
```

- [ ] **Step 3: Adicionar porta 2222 ao sshd_config**

```bash
sudo nano /etc/ssh/sshd_config
```

Localizar a linha `Port 22` (ou adicionar no topo do arquivo se não existir) e deixar assim:

```
Port 22
Port 2222
```

Salvar: `Ctrl+O`, `Enter`, `Ctrl+X`

- [ ] **Step 4: Verificar sintaxe antes de reiniciar**

```bash
sudo sshd -t
```

Esperado: nenhuma saída (sem erros)

- [ ] **Step 5: Reiniciar SSH**

```bash
sudo systemctl restart ssh
```

- [ ] **Step 6: Verificar que porta 2222 está escutando**

```bash
sudo ss -tlnp | grep 2222
```

Esperado:
```
LISTEN 0 128 0.0.0.0:2222 0.0.0.0:* users:(("sshd",...))
LISTEN 0 128    [::]:2222    [::]:* users:(("sshd",...))
```

- [ ] **Step 7: Testar acesso via porta 2222 (em outro terminal — NÃO feche o atual)**

Abrir **novo terminal** no seu computador local e testar:

```bash
ssh -p 2222 root@<IP_DA_VPS>
```

Esperado: login bem-sucedido. Se falhar, **não prossiga** — revisar os steps anteriores.

---

### Task 2: Configurar e ativar ufw

**Contexto:** Com porta 2222 confirmada funcionando, configurar as regras do firewall e ativá-lo. A ordem das regras importa.

**Arquivos:**
- Configuração via comandos ufw (na VPS)

- [ ] **Step 1: Descobrir seu IP fixo atual**

No seu computador local (não na VPS):

```bash
curl -s https://api.ipify.org
```

Anotar o IP retornado — será usado como `<SEU_IP>` nos próximos steps.

- [ ] **Step 2: Definir política padrão — bloquear entrada, permitir saída**

Na VPS:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

- [ ] **Step 3: Liberar SSH na porta 22 apenas para seu IP**

```bash
sudo ufw allow from <SEU_IP> to any port 22 proto tcp
```

Substituir `<SEU_IP>` pelo IP obtido no Step 1.

- [ ] **Step 4: Liberar porta 2222 para o mundo (CI/CD)**

```bash
sudo ufw allow 2222/tcp
```

- [ ] **Step 5: Liberar HTTP e HTTPS para o Nginx**

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

- [ ] **Step 6: Revisar regras antes de ativar**

```bash
sudo ufw show added
```

Esperado — deve listar exatamente estas regras (sem mais, sem menos):
```
ufw allow from <SEU_IP> to any port 22 proto tcp
ufw allow 2222/tcp
ufw allow 80/tcp
ufw allow 443/tcp
```

- [ ] **Step 7: Ativar ufw**

```bash
sudo ufw enable
```

Responder `y` quando perguntado. O sistema avisa que pode interromper conexões SSH existentes — é seguro prosseguir porque a regra do seu IP já está configurada.

- [ ] **Step 8: Verificar status final**

```bash
sudo ufw status verbose
```

Esperado:
```
Status: active
...
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    <SEU_IP>
2222/tcp                   ALLOW IN    Anywhere
80/tcp                     ALLOW IN    Anywhere
443/tcp                    ALLOW IN    Anywhere
```

- [ ] **Step 9: Testar acesso SSH do seu computador local (novo terminal)**

```bash
ssh root@<IP_DA_VPS>
```

Esperado: login bem-sucedido na porta 22. Se falhar, usar o Console Web da Hostinger para reverter: `sudo ufw disable`.

---

### Task 3: Desabilitar CUPS

**Contexto:** CUPS é um serviço de impressão sem utilidade em servidor. Estava expondo a porta 631 publicamente.

**Arquivos:**
- Configuração via systemd (na VPS)

- [ ] **Step 1: Parar os serviços CUPS**

```bash
sudo systemctl stop cups 2>/dev/null; sudo systemctl stop cups-browsed 2>/dev/null; true
```

- [ ] **Step 2: Desabilitar para não iniciar no boot**

```bash
sudo systemctl disable cups 2>/dev/null; sudo systemctl disable cups-browsed 2>/dev/null; true
```

- [ ] **Step 3: Verificar que porta 631 não está mais escutando**

```bash
sudo ss -tlnp | grep 631
```

Esperado: nenhuma saída (porta fechada).

- [ ] **Step 4: Verificar que os outros serviços continuam rodando**

```bash
sudo systemctl status jtasks jtasks-bot nginx
```

Esperado: todos com `Active: active (running)`.

---

### Task 4: Atualizar CI/CD para usar porta 2222

**Contexto:** O GitHub Actions usa SSH para fazer deploy. Com a porta 22 restrita ao IP fixo, o CI/CD precisa usar a porta 2222.

**Arquivos:**
- Modificar: `.github/workflows/deploy.yml`

- [ ] **Step 1: Editar o workflow localmente**

Abrir [.github/workflows/deploy.yml](.github/workflows/deploy.yml) e adicionar `port: 2222`:

```yaml
name: Deploy to VPS
# Auto-deploy on push to master

on:
  push:
    branches:
      - master

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          port: 2222
          script: |
            set -e
            git config --global --add safe.directory /home/jtasks/JtasksApp
            cd /home/jtasks/JtasksApp
            git fetch origin master
            git reset --hard origin/master
            source venv/bin/activate
            pip install -r requirements.txt --quiet
            sudo systemctl restart jtasks
            sudo systemctl restart jtasks-bot
```

- [ ] **Step 2: Commit e push**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: usar porta 2222 para deploy SSH após hardening de firewall"
git push origin master
```

- [ ] **Step 3: Verificar que o CI/CD passou**

No GitHub, acessar a aba **Actions** do repositório e confirmar que o workflow `Deploy to VPS` completou com sucesso (check verde).

- [ ] **Step 4: Verificar que a aplicação está rodando após o deploy**

```bash
curl -s -o /dev/null -w "%{http_code}" https://<SEU_DOMINIO>/
```

Esperado: `200` ou `302`.

---

### Task 5: Verificação final

**Contexto:** Confirmar o estado completo da VPS após todas as mudanças.

- [ ] **Step 1: Verificar portas abertas**

Na VPS:

```bash
sudo ss -tlnp
```

Esperado — exatamente estas portas:
```
0.0.0.0:22    → sshd (restrito pelo ufw ao seu IP)
0.0.0.0:2222  → sshd (aberto para CI/CD)
0.0.0.0:80    → nginx
0.0.0.0:443   → nginx
127.0.0.1:8080 → gunicorn (só local, não exposto)
127.0.0.53:53  → systemd-resolved (interno)
```

Porta 631 **não deve aparecer**.

- [ ] **Step 2: Verificar regras do firewall**

```bash
sudo ufw status verbose
```

Esperado: status `active` com as 4 regras definidas na Task 2.

- [ ] **Step 3: Verificar serviços ativos**

```bash
sudo systemctl list-units --type=service --state=running | grep -E "(jtasks|nginx|ssh)"
```

Esperado:
```
jtasks-bot.service   loaded active running JtasksApp Telegram Bot
jtasks.service       loaded active running Jtasks FastAPI App
nginx.service        loaded active running A high performance web server
ssh.service          loaded active running OpenBSD Secure Shell server
```

- [ ] **Step 4: Testar acesso à aplicação web**

No browser ou via curl, acessar `https://<SEU_DOMINIO>/` e confirmar que a aplicação carrega normalmente.

- [ ] **Step 5: Testar bot Telegram**

Enviar uma mensagem para o bot do JtasksApp e para o Hermes via Telegram e confirmar que ambos respondem.
