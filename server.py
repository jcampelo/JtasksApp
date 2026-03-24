import http.server
import json
import os
import threading
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime

DATA_FILE   = os.path.join(os.path.dirname(__file__), "data.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
PORT = 8080


# ── CONFIG ──────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── EMAIL ────────────────────────────────────────────────────────────

def build_email_html():
    """Lê data.json e monta o HTML do resumo de atividades."""
    if not os.path.exists(DATA_FILE):
        active, completed = [], []
    else:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            active    = data.get("today", {}).get("active", [])
            completed = data.get("today", {}).get("completed", [])
        except Exception:
            active, completed = [], []

    today_iso = date.today().isoformat()
    today_dt  = date.today()

    # Formata data por extenso
    MESES = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    DIAS  = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
             "Sexta-feira","Sábado","Domingo"]
    dia_semana = DIAS[today_dt.weekday()]
    data_fmt   = f"{dia_semana}, {today_dt.day} de {MESES[today_dt.month-1]} de {today_dt.year}"

    # Classifica por deadline
    overdue  = []
    due_soon = []
    for task in active:
        dl = task.get("deadline")
        if not dl:
            continue
        diff = (date.fromisoformat(dl) - today_dt).days
        if diff < 0:
            overdue.append((task, abs(diff)))
        elif diff <= 3:
            due_soon.append((task, diff))
    overdue.sort(key=lambda x: x[1], reverse=True)
    due_soon.sort(key=lambda x: x[1])

    # Contagem por prioridade
    criticas = [t for t in active if t.get("priority") == "critica"]
    urgentes = [t for t in active if t.get("priority") == "urgente"]
    normais  = [t for t in active if t.get("priority") == "normal"]

    total = len(active) + len(completed)
    taxa  = f"{round(len(completed)/total*100)}%" if total else "—"

    # Helpers de HTML
    def pri_badge(p):
        colors = {"critica": ("#fff1f2","#e63946","🔴 Crítica"),
                  "urgente": ("#fff7ed","#ea580c","🟡 Urgente"),
                  "normal":  ("#f1f5f9","#64748b","⚪ Normal")}
        bg, color, label = colors.get(p, ("#f1f5f9","#64748b", p))
        return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:4px;font-size:0.78rem;font-weight:700;">{label}</span>'

    def task_row(task, badge_text, badge_color):
        name    = task.get("name","—")
        project = task.get("project","")
        pri     = task.get("priority","normal")
        proj_html = f' &nbsp;<span style="color:#64748b;font-size:0.8rem;">📁 {project}</span>' if project else ""
        return f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;">
            <div style="font-weight:600;color:#1a1a2e;margin-bottom:4px;">{name}</div>
            <div>{pri_badge(pri)}{proj_html}
              &nbsp;<span style="background:{badge_color[0]};color:{badge_color[1]};padding:2px 8px;border-radius:4px;font-size:0.78rem;font-weight:700;">{badge_text}</span>
            </div>
          </td>
        </tr>"""

    # Seção de alertas
    alert_html = ""
    if overdue or due_soon:
        rows = ""
        for task, days in overdue:
            rows += task_row(task, f"⚠ {days}d em atraso", ("#fff1f2","#e63946"))
        for task, days in due_soon:
            label = "🔔 Vence hoje" if days == 0 else f"⏰ {days}d restantes"
            rows += task_row(task, label, ("#fff7ed","#ea580c"))

        alert_html = f"""
        <tr>
          <td style="padding:20px 28px 0;">
            <h2 style="font-size:0.82rem;color:#e63946;text-transform:uppercase;letter-spacing:0.8px;margin:0 0 12px;">⚠ Alertas de Prazo</h2>
            <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
          </td>
        </tr>"""

    # Seção prioridades
    def pri_row(icon, label, count, color):
        return f"""
        <tr>
          <td style="padding:6px 0;border-bottom:1px solid #f8fafc;">
            <span style="color:{color};font-weight:700;">{icon} {label}</span>
            <span style="float:right;font-weight:800;color:#1a1a2e;">{count}</span>
          </td>
        </tr>"""

    pri_html = ""
    if active:
        pri_html = f"""
        <tr>
          <td style="padding:20px 28px 0;">
            <h2 style="font-size:0.82rem;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;margin:0 0 12px;">Por Prioridade</h2>
            <table width="100%" cellpadding="0" cellspacing="0">
              {pri_row("🔴","Crítica", len(criticas),"#e63946")}
              {pri_row("🟡","Urgente", len(urgentes),"#ea580c")}
              {pri_row("⚪","Normal",  len(normais), "#64748b")}
            </table>
          </td>
        </tr>"""
    else:
        pri_html = """
        <tr>
          <td style="padding:20px 28px;text-align:center;color:#94a3b8;font-size:0.9rem;">
            Nenhuma atividade ativa no momento.
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;">
  <tr><td align="center" style="padding:24px 16px;">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.10);max-width:600px;">

      <!-- HEADER -->
      <tr>
        <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                   padding:24px 28px;border-bottom:3px solid #e63946;">
          <h1 style="color:#ffffff;margin:0;font-size:1.35rem;font-weight:800;letter-spacing:0.5px;">Jabil Notes</h1>
          <p style="color:rgba(255,255,255,0.65);margin:6px 0 0;font-size:0.83rem;">{data_fmt}</p>
        </td>
      </tr>

      {alert_html}
      {pri_html}

      <!-- TOTAIS -->
      <tr>
        <td style="padding:20px 28px 0;">
          <h2 style="font-size:0.82rem;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;margin:0 0 12px;">Resumo do Dia</h2>
        </td>
      </tr>
      <tr>
        <td style="padding:0 28px 20px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f8fafc;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="text-align:center;padding:16px 8px;">
                <div style="font-size:1.8rem;font-weight:800;color:#e63946;line-height:1;">{len(active)}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Ativas</div>
              </td>
              <td style="text-align:center;padding:16px 8px;border-left:1px solid #e2e8f0;">
                <div style="font-size:1.8rem;font-weight:800;color:#22c55e;line-height:1;">{len(completed)}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Concluídas</div>
              </td>
              <td style="text-align:center;padding:16px 8px;border-left:1px solid #e2e8f0;">
                <div style="font-size:1.8rem;font-weight:800;color:#3b82f6;line-height:1;">{taxa}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">Taxa do dia</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="background:#1a1a2e;padding:14px 28px;text-align:center;">
          <p style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin:0;">
            Jabil Notes — relatório gerado automaticamente em {today_iso}
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body></html>"""

    subject = f"Jabil Notes — Resumo {today_iso}"
    return html, subject


def send_email(cfg, html_body, subject):
    """Envia email via SMTP com STARTTLS (porta 587) ou SSL (porta 465)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["smtp_user"]
    msg["To"]      = cfg["email_to"]
    msg.attach(MIMEText("Abra este email em um cliente que suporte HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    port = int(cfg.get("smtp_port", 587))
    host = cfg["smtp_host"]
    ctx  = ssl.create_default_context()

    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as smtp:
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.sendmail(cfg["smtp_user"], cfg["email_to"], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.sendmail(cfg["smtp_user"], cfg["email_to"], msg.as_string())


# ── SCHEDULER ────────────────────────────────────────────────────────

_sched_stop = threading.Event()

def scheduler_loop():
    """Daemon thread: verifica a cada 30s se é hora de enviar o email diário."""
    last_sent_date = None
    while not _sched_stop.is_set():
        try:
            cfg = load_config()
            if cfg.get("enabled") and cfg.get("smtp_user") and cfg.get("email_to"):
                h, m = map(int, cfg.get("schedule_time", "08:00").split(":"))
                now   = datetime.now()
                today = now.date().isoformat()
                if now.hour == h and now.minute == m and last_sent_date != today:
                    html, subject = build_email_html()
                    send_email(cfg, html, subject)
                    last_sent_date = today
                    print(f"[scheduler] Email enviado: {subject}")
        except Exception as e:
            print(f"[scheduler] Erro: {e}")
        _sched_stop.wait(30)


# ── HTTP HANDLER ──────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path, content_type):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_file(os.path.join(os.path.dirname(__file__), "index.html"), "text/html; charset=utf-8")

        elif self.path == "/data":
            if not os.path.exists(DATA_FILE):
                self._send_json(200, {}); return
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self._send_json(200, json.load(f))
            except Exception:
                self._send_json(500, {"error": "read_failed"})

        elif self.path == "/config":
            cfg = load_config()
            safe = {k: v for k, v in cfg.items() if k != "smtp_password"}
            safe["has_password"] = bool(cfg.get("smtp_password"))
            self._send_json(200, safe)

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/data":
            body = self._read_body()
            try:
                data = json.loads(body)
            except Exception:
                self._send_json(400, {"error": "invalid_json"}); return
            try:
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._send_json(200, {"ok": True})
            except Exception:
                self._send_json(500, {"error": "write_failed"})

        elif self.path == "/config":
            body = self._read_body()
            try:
                new_cfg = json.loads(body)
            except Exception:
                self._send_json(400, {"error": "invalid_json"}); return
            # Mantém senha existente se não foi enviada nova
            existing = load_config()
            if not new_cfg.get("smtp_password"):
                new_cfg["smtp_password"] = existing.get("smtp_password", "")
            try:
                save_config(new_cfg)
                self._send_json(200, {"ok": True})
            except Exception:
                self._send_json(500, {"error": "write_failed"})

        elif self.path == "/notify/send":
            cfg = load_config()
            if not cfg.get("email_to") or not cfg.get("smtp_user") or not cfg.get("smtp_host"):
                self._send_json(400, {"error": "Configuração incompleta. Preencha todos os campos SMTP."}); return
            if not cfg.get("smtp_password"):
                self._send_json(400, {"error": "Senha SMTP não configurada."}); return
            try:
                html, subject = build_email_html()
                send_email(cfg, html, subject)
                self._send_json(200, {"ok": True, "subject": subject})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    t = threading.Thread(target=scheduler_loop, name="email-scheduler", daemon=True)
    t.start()
    print(f"[scheduler] Iniciado — verificação a cada 30s")
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Jabil Notes rodando em http://0.0.0.0:{PORT}")
    server.serve_forever()
