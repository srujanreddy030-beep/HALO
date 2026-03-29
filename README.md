# AI-Powered Lone Worker Safety & Productivity Monitoring

Real-time AI safety system using **YOLOv8** + **MediaPipe Pose** to detect worker falls, PPE violations, and extended idleness — with **instant email & Telegram alerts**.

## Features

| Feature | Description |
|---------|-------------|
| 🔴 **Fall Detection** | MediaPipe Pose landmarks analyze torso angle; alerts on sustained lying posture |
| 🟠 **PPE Compliance** | Detects missing helmets/vests (requires custom PPE model) |
| 🟡 **Idle Monitoring** | Alerts when a worker hasn't moved for a configurable threshold |
| 📧 **Email Alerts** | Professional HTML emails with severity-colored headers + inline incident snapshots |
| 📱 **Telegram Alerts** | Instant Telegram messages with photos |
| 🔊 **Sound Alerts** | Audible beeps on incidents (Windows) |
| 📊 **Live Dashboard** | Streamlit dashboard with KPIs, live feed, snapshot gallery, alert status |
| 🗄️ **Incident Logging** | SQLite database with full incident history |

## Project Layout

```
LoneWorkerSafety/
  main.py               # Detection loop (camera → YOLO → pose → alerts)
  dashboard.py           # Streamlit monitoring dashboard
  requirements.txt
  .env.example           # Configuration template (copy → .env)
  worker_safety.db       # SQLite incident database (auto-created)
  utils/
    alerts.py            # Email (HTML) + Telegram + delivery log
    database.py          # SQLite incident storage
    detection.py         # YOLOv8 person + PPE detection
    pose.py              # MediaPipe Pose + box-heuristic fallback
    tracking.py          # Simple centroid tracker
    sound_alert.py       # Windows audible alarm
```

## Setup (Windows PowerShell)

### 1. Create virtual environment

```powershell
cd .\LoneWorkerSafety
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure alerts

```powershell
copy .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `EMAIL_USER` | Your Gmail address |
| `EMAIL_PASSWORD` | **Gmail App Password** (NOT your normal password!) |
| `ALERT_RECIPIENT_EMAILS` | Comma-separated recipient emails |

#### Getting a Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required first)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create a new app password for **Mail**
5. Copy the 16-character password into `.env`

### 3. Run

**Terminal 1** (detection loop):
```powershell
python .\main.py
```

**Terminal 2** (dashboard):
```powershell
streamlit run .\dashboard.py
```

## How Alerts Work

```
Camera Feed → YOLOv8 Person Detection → MediaPipe Pose Analysis
                                              ↓
                                    Posture Classification
                                    (standing/sitting/lying)
                                              ↓
                                    ┌─────────────────────┐
                                    │  Danger Detected?    │
                                    │  (fall / no PPE /    │
                                    │   idle too long)     │
                                    └─────────┬───────────┘
                                              ↓
                              ┌───────────────┼───────────────┐
                              ↓               ↓               ↓
                         📧 Email        📱 Telegram     🔊 Sound
                        (HTML +           (photo)        (beep)
                        snapshot)
```

## Notes / Limitations (Prototype)

- PPE detection is **stubbed by default** (returns "unknown") unless you provide a PPE model via `PPE_MODEL` env var.
- Multi-person tracking is a simple centroid matcher (good enough for demos).
- Fall detection uses **MediaPipe Pose** torso angle + bounding box geometry, but is NOT a medical-grade fall classifier.
- Email requires Gmail with App Password (or any SMTP server — change `EMAIL_HOST` / `EMAIL_PORT` in `.env`).
