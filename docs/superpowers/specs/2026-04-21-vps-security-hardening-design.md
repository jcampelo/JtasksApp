# VPS Security Hardening — Design Spec

**Data:** 2026-04-21  
**Projeto:** JtasksApp (Hostinger VPS)  
**Escopo:** Ativar firewall, restringir SSH, desabilitar serviços desnecessários

---

## Contexto

A VPS roda os seguintes serviços:
- **jtasks.service** — FastAPI/gunicorn em `127.0.0.1:8080`, proxiado pelo Nginx
- **jtasks-bot.service** — Bot Telegram do JtasksApp (somente conexões de saída)
- **Hermes agente** — Roda como root em `/root/.hermes/`, bot Telegram (somente conexões de saída)
- **Nginx** — Reverse proxy nas portas 80/443
- **sshd** — Porta 22, atualmente aberta para o mundo inteiro
- **CUPS (cupsd)** — Porta 631, serviço de impressão, desnecessário em servidor

**Problemas identificados:**
1. `ufw` inativo — nenhum firewall local
2. SSH (porta 22) aberto para qualquer IP
3. CUPS exposto na porta 631 sem necessidade
4. CI/CD (GitHub Actions) usa SSH com IP variável — impede restrição total da porta 22

---

## Solução

### Estratégia Híbrida para SSH
- **Porta 22:** restrita ao IP fixo do usuário — acesso pessoal
- **Porta 2222:** aberta para o mundo — usada exclusivamente pelo CI/CD (GitHub Actions)
- Bots Telegram (JtasksApp e Hermes) não são afetados — só fazem conexões de saída

### Componentes

#### 1. ufw — Firewall local

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow from <SEU_IP_FIXO> to any port 22    # SSH pessoal
ufw allow 2222/tcp                              # SSH para CI/CD
ufw allow 80/tcp                                # HTTP (Nginx)
ufw allow 443/tcp                               # HTTPS (Nginx)
ufw enable
```

#### 2. sshd — Porta adicional

Adicionar ao `/etc/ssh/sshd_config`:
```
Port 22
Port 2222
```

Reiniciar: `sudo systemctl restart ssh`

#### 3. CUPS — Desabilitar

```bash
sudo systemctl stop cups cupsd cups-browsed 2>/dev/null
sudo systemctl disable cups cupsd cups-browsed 2>/dev/null
```

#### 4. GitHub Actions — Atualizar porta

Em `.github/workflows/deploy.yml`, adicionar `port: 2222` na action `appleboy/ssh-action`:

```yaml
- name: Deploy via SSH
  uses: appleboy/ssh-action@v1
  with:
    host: ${{ secrets.VPS_HOST }}
    username: ${{ secrets.VPS_USER }}
    key: ${{ secrets.VPS_SSH_KEY }}
    port: 2222        # <-- adicionar esta linha
    script: |
      ...
```

---

## Estado Final das Portas

| Porta | Protocolo | Quem acessa | Status |
|-------|-----------|-------------|--------|
| 22 | TCP | Só IP fixo do usuário | ✅ Restrito |
| 80 | TCP | Mundo todo | ✅ Nginx |
| 443 | TCP | Mundo todo | ✅ Nginx |
| 631 | TCP | — | 🔴 Fechado/desabilitado |
| 2222 | TCP | GitHub Actions (CI/CD) | ✅ Aberto |

---

## Impacto por Serviço

| Serviço | Impacto |
|---------|---------|
| JtasksApp (web) | Nenhum — continua via Nginx |
| Bot Telegram JtasksApp | Nenhum — conexão de saída |
| Hermes agente | Nenhum — conexão de saída |
| CI/CD GitHub Actions | Requer `port: 2222` no workflow |
| Acesso SSH pessoal | Funciona na porta 22 com IP fixo |

---

## Ordem de Execução (crítica)

A ordem importa para não se trancar fora do servidor:

1. Adicionar porta 2222 ao `sshd_config` e reiniciar SSH
2. **Verificar que porta 2222 está acessível** antes de ativar ufw
3. Configurar regras do ufw (sem ativar ainda)
4. Ativar ufw
5. Desabilitar CUPS
6. Atualizar `deploy.yml` e fazer push para testar CI/CD

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Perder acesso SSH se IP mudar | Console web da Hostinger (VPS Console) como acesso de emergência |
| CUPS necessário por alguma razão | Improvável em servidor — verificar antes de desabilitar |
| GitHub Actions falhar após mudança de porta | Testar CI/CD imediatamente após deploy do workflow atualizado |
