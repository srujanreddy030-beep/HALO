"""
HALO Keep-Alive — Prevents Streamlit Cloud from sleeping.

Pings your deployed app every 5 minutes so it stays online 24/7.

Usage:
  python keep_alive.py
  python keep_alive.py --url https://your-app.streamlit.app
  python keep_alive.py --interval 3    (ping every 3 minutes)

Run this on your laptop before your inspection and leave it open.
The app will NEVER go offline as long as this script is running.
"""

import argparse
import os
import time
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


class C:
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


def ping_app(url: str) -> bool:
    """Send a request to keep the app alive."""
    try:
        resp = requests.get(url, timeout=30)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def main():
    parser = argparse.ArgumentParser(description="HALO Keep-Alive")
    parser.add_argument("--url", type=str,
                        default=os.getenv("STREAMLIT_CLOUD_URL", ""),
                        help="Your Streamlit Cloud URL")
    parser.add_argument("--interval", type=int, default=5,
                        help="Ping interval in minutes (default: 5)")
    args = parser.parse_args()

    url = args.url.strip()
    if not url:
        print(f"\n{C.RED}  ✗ No URL provided!{C.RESET}")
        print(f"  {C.YELLOW}Set STREAMLIT_CLOUD_URL in .env or pass --url{C.RESET}")
        print(f"  {C.DIM}  Example: python keep_alive.py --url https://your-app.streamlit.app{C.RESET}\n")
        sys.exit(1)

    interval_s = args.interval * 60

    print(f"""
{C.CYAN}{C.BOLD}  ╔═══════════════════════════════════════════════╗
  ║        HALO Keep-Alive Service                ║
  ╚═══════════════════════════════════════════════╝{C.RESET}

  {C.BOLD}URL:{C.RESET}       {C.CYAN}{url}{C.RESET}
  {C.BOLD}Interval:{C.RESET}  Every {args.interval} minutes
  {C.BOLD}Status:{C.RESET}    Running... (press Ctrl+C to stop)
""")

    ping_count = 0
    fail_count = 0

    try:
        while True:
            ping_count += 1
            now = datetime.now().strftime("%H:%M:%S")
            
            success = ping_app(url)
            
            if success:
                print(f"  {C.GREEN}✓{C.RESET} [{now}] Ping #{ping_count} — {C.GREEN}App is ONLINE{C.RESET}")
            else:
                fail_count += 1
                print(f"  {C.RED}✗{C.RESET} [{now}] Ping #{ping_count} — {C.RED}App not responding (attempt {fail_count}){C.RESET}")
                if fail_count >= 3:
                    print(f"  {C.YELLOW}  ⚠ App may need manual restart on Streamlit Cloud{C.RESET}")

            time.sleep(interval_s)

    except KeyboardInterrupt:
        print(f"\n  {C.CYAN}Keep-alive stopped. Total pings: {ping_count}{C.RESET}\n")


if __name__ == "__main__":
    main()
