"""
HALO Alert System — Email & Telegram notifications with professional HTML emails,
inline incident snapshots, retry logic, and delivery logging.
"""

import json
import os
import smtplib
import ssl
import time
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Iterable, Optional

import requests


# ---------------------------------------------------------------------------
# Alert delivery log (JSON Lines file next to the DB)
# ---------------------------------------------------------------------------
_ALERT_LOG_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "alert_log.jsonl"


def _log_alert_delivery(
    channel: str,
    success: bool,
    subject: str = "",
    recipients: str = "",
    error: str = "",
) -> None:
    """Append one line to the delivery log."""
    _ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "success": success,
        "subject": subject,
        "recipients": recipients,
        "error": error,
    }
    try:
        with open(_ALERT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_recent_alert_log(limit: int = 20) -> list[dict]:
    """Return the most recent *limit* alert deliveries (newest first)."""
    if not _ALERT_LOG_PATH.exists():
        return []
    try:
        lines = _ALERT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
        entries = [json.loads(line) for line in lines[-limit:]]
        entries.reverse()
        return entries
    except (OSError, json.JSONDecodeError):
        return []


# ---------------------------------------------------------------------------
# Telegram alerts
# ---------------------------------------------------------------------------
def send_telegram_alert(
    message: str,
    *,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    image_path: Optional[str] = None,
    timeout_s: int = 15,
) -> bool:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    base = f"https://api.telegram.org/bot{token}"
    try:
        if image_path and Path(image_path).exists():
            with open(image_path, "rb") as f:
                resp = requests.post(
                    f"{base}/sendPhoto",
                    data={"chat_id": chat_id, "caption": message},
                    files={"photo": f},
                    timeout=timeout_s,
                )
        else:
            resp = requests.post(
                f"{base}/sendMessage",
                data={"chat_id": chat_id, "text": message},
                timeout=timeout_s,
            )
        success = resp.ok
        _log_alert_delivery("telegram", success, subject=message[:80])
        return success
    except requests.RequestException as exc:
        _log_alert_delivery("telegram", False, subject=message[:80], error=str(exc))
        return False


# ---------------------------------------------------------------------------
# SMS Alerts via Twilio
# ---------------------------------------------------------------------------
def send_sms_alert(message: str) -> bool:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    recipient_phone = os.getenv("ALERT_RECIPIENT_PHONE")

    if not all([account_sid, auth_token, from_number, recipient_phone]):
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "To": recipient_phone,
        "From": from_number,
        "Body": message
    }

    try:
        resp = requests.post(
            url,
            auth=(account_sid, auth_token),
            data=data,
            timeout=10,
        )
        success = resp.ok
        _log_alert_delivery("sms", success, subject=message[:80])
        return success
    except requests.RequestException as exc:
        _log_alert_delivery("sms", False, subject=message[:80], error=str(exc))
        return False


def is_sms_configured() -> bool:
    """Quick check whether Twilio credentials are present."""
    return bool(
        os.getenv("TWILIO_ACCOUNT_SID")
        and os.getenv("TWILIO_AUTH_TOKEN")
        and os.getenv("TWILIO_FROM_NUMBER")
        and os.getenv("ALERT_RECIPIENT_PHONE")
    )


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------
_SEVERITY_COLORS = {
    "CRITICAL": {"bg": "#DC2626", "label": "🔴 CRITICAL — IMMEDIATE ACTION REQUIRED"},
    "HIGH":     {"bg": "#EA580C", "label": "🟠 HIGH — Safety Violation Detected"},
    "MEDIUM":   {"bg": "#D97706", "label": "🟡 MEDIUM — Attention Needed"},
    "LOW":      {"bg": "#2563EB", "label": "🔵 LOW — Informational"},
    "INFO":     {"bg": "#6B7280", "label": "ℹ️ INFO"},
}


def _build_html_email(
    subject: str,
    body: str,
    severity: str = "CRITICAL",
    *,
    track_id: Optional[int] = None,
    has_image: bool = False,
) -> str:
    sev = _SEVERITY_COLORS.get(severity.upper(), _SEVERITY_COLORS["CRITICAL"])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    track_row = ""
    if track_id is not None:
        track_row = f"""
        <tr>
          <td style="padding:6px 12px;color:#6B7280;font-size:13px;">Worker ID</td>
          <td style="padding:6px 12px;font-weight:700;font-size:13px;">Track #{track_id}</td>
        </tr>"""

    image_section = ""
    if has_image:
        image_section = """
        <div style="margin-top:20px;">
          <p style="color:#6B7280;font-size:13px;margin-bottom:8px;">📸 Incident Snapshot:</p>
          <img src="cid:incident_snapshot" alt="Incident Snapshot"
               style="max-width:100%;border-radius:10px;border:1px solid #E5E7EB;box-shadow:0 4px 12px rgba(0,0,0,0.1);" />
        </div>"""

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:600px;margin:20px auto;background:#FFFFFF;border-radius:16px;overflow:hidden;
              box-shadow:0 10px 40px rgba(0,0,0,0.12);">

    <!-- Severity Banner -->
    <div style="background:{sev['bg']};padding:20px 24px;text-align:center;">
      <h1 style="color:#FFFFFF;margin:0;font-size:18px;font-weight:800;letter-spacing:0.5px;">
        {sev['label']}
      </h1>
    </div>

    <!-- Body -->
    <div style="padding:24px;">
      <h2 style="color:#111827;margin:0 0 12px;font-size:20px;">{subject}</h2>
      <p style="color:#374151;font-size:15px;line-height:1.6;margin:0 0 16px;">{body}</p>

      <!-- Details Table -->
      <table style="width:100%;border-collapse:collapse;background:#F9FAFB;border-radius:10px;overflow:hidden;
                     border:1px solid #E5E7EB;">
        <tr>
          <td style="padding:6px 12px;color:#6B7280;font-size:13px;">Timestamp</td>
          <td style="padding:6px 12px;font-weight:700;font-size:13px;">{ts}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:#6B7280;font-size:13px;">Severity</td>
          <td style="padding:6px 12px;font-weight:700;font-size:13px;color:{sev['bg']};">{severity.upper()}</td>
        </tr>{track_row}
      </table>

      {image_section}
    </div>

    <!-- Footer -->
    <div style="background:#F9FAFB;padding:14px 24px;text-align:center;border-top:1px solid #E5E7EB;">
      <p style="margin:0;color:#9CA3AF;font-size:11px;">
        HALO — Hazard Analytics &amp; Live Oversight • Automated Safety Alert
      </p>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Parse recipients
# ---------------------------------------------------------------------------
def _parse_recipients(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Email sending (with retry)
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0


def send_email_alert(
    subject: str,
    body: str,
    *,
    image_path: Optional[str] = None,
    recipients: Optional[Iterable[str]] = None,
    severity: str = "CRITICAL",
    track_id: Optional[int] = None,
) -> bool:
    """
    Send a professional HTML email with an optional inline incident snapshot.

    Retries up to 3 times with exponential backoff on failure.

    Required env vars (Gmail example):
      EMAIL_HOST=smtp.gmail.com
      EMAIL_PORT=587
      EMAIL_USER=youraddress@gmail.com
      EMAIL_PASSWORD=your_app_password
      ALERT_RECIPIENT_EMAILS=gm1@gmail.com,gm2@gmail.com
    """
    host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    port = int(os.getenv("EMAIL_PORT", "587"))
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")

    env_recipients = _parse_recipients(os.getenv("ALERT_RECIPIENT_EMAILS"))
    to_list = list(recipients) if recipients is not None else env_recipients

    if not user or not password or not to_list:
        # Email not configured — fail silently.
        return False

    has_image = bool(image_path and Path(image_path).exists())
    html = _build_html_email(
        subject, body, severity, track_id=track_id, has_image=has_image,
    )

    # Build MIME message with inline image
    msg = MIMEMultipart("related")
    msg["Subject"] = f"[HALO {severity.upper()}] {subject}"
    msg["From"] = user
    msg["To"] = ", ".join(to_list)
    msg["X-Priority"] = "1" if severity.upper() == "CRITICAL" else "3"

    msg.attach(MIMEText(html, "html"))

    if has_image:
        try:
            with open(image_path, "rb") as f:
                img_data = f.read()
            img_mime = MIMEImage(img_data, _subtype="jpeg")
            img_mime.add_header("Content-ID", "<incident_snapshot>")
            img_mime.add_header(
                "Content-Disposition", "inline", filename=Path(image_path).name,
            )
            msg.attach(img_mime)
        except OSError:
            pass

    # Retry loop
    last_err = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(msg)
            _log_alert_delivery(
                "email", True,
                subject=subject, recipients=", ".join(to_list),
            )
            return True
        except OSError as exc:
            last_err = f"Attempt {attempt}/{_MAX_RETRIES}: {exc}"
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_S * attempt)

    _log_alert_delivery(
        "email", False,
        subject=subject, recipients=", ".join(to_list), error=last_err,
    )
    return False


def is_email_configured() -> bool:
    """Quick check whether email credentials are present."""
    return bool(
        os.getenv("EMAIL_USER")
        and os.getenv("EMAIL_PASSWORD")
        and _parse_recipients(os.getenv("ALERT_RECIPIENT_EMAILS"))
    )


def is_telegram_configured() -> bool:
    """Quick check whether Telegram credentials are present."""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))

