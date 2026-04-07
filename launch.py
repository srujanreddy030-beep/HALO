"""
HALO — One-Click Launcher
==========================
Starts everything in one shot:
  1. Streamlit Dashboard
  2. Ngrok public tunnel
  3. AI Monitoring Engine (optional)

Usage:
  python launch.py                 # Dashboard + Ngrok (no camera)
  python launch.py --monitor       # Dashboard + Ngrok + Camera AI

Press Ctrl+C to stop everything gracefully.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

ROOT = Path(__file__).parent
VENV_PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")

# Use venv python if it exists, otherwise system python
PYTHON = VENV_PYTHON if Path(VENV_PYTHON).exists() else sys.executable

# ── ANSI colors for beautiful terminal output ──
class C:
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"

LOGO = f"""
{C.CYAN}{C.BOLD}
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║     ██╗  ██╗ █████╗ ██╗      ██████╗                  ║
  ║     ██║  ██║██╔══██╗██║     ██╔═══██╗                 ║
  ║     ███████║███████║██║     ██║   ██║                 ║
  ║     ██╔══██║██╔══██║██║     ██║   ██║                 ║
  ║     ██║  ██║██║  ██║███████╗╚██████╔╝                 ║
  ║     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝                 ║
  ║                                                       ║
  ║     Hazard Analytics & Live Oversight                  ║
  ║     AI-Powered Lone Worker Safety System               ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
{C.RESET}"""

processes: list[subprocess.Popen] = []
ngrok_tunnel = None


def print_step(icon: str, msg: str, color: str = C.GREEN):
    print(f"  {color}{icon}  {msg}{C.RESET}")


def print_divider():
    print(f"  {C.DIM}{'─' * 55}{C.RESET}")


def cleanup(*_args):
    """Gracefully shut down all services."""
    print(f"\n{C.YELLOW}  ⏳  Shutting down HALO services...{C.RESET}")

    # Close ngrok tunnel
    global ngrok_tunnel
    if ngrok_tunnel:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(ngrok_tunnel.public_url)
            ngrok.kill()
            print_step("✓", "Ngrok tunnel closed", C.GREEN)
        except Exception:
            pass

    # Terminate subprocesses
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print_step("✓", "All services stopped", C.GREEN)
    print(f"\n  {C.CYAN}Thank you for using HALO! 🛡️{C.RESET}\n")
    sys.exit(0)


def start_streamlit() -> subprocess.Popen:
    """Launch the Streamlit dashboard."""
    print_step("🚀", "Starting Streamlit Dashboard...", C.CYAN)

    dashboard_path = str(ROOT / "dashboard.py")
    port = os.getenv("STREAMLIT_PORT", "8501")

    proc = subprocess.Popen(
        [
            PYTHON, "-m", "streamlit", "run", dashboard_path,
            "--server.port", port,
            "--server.headless", "true",
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    processes.append(proc)

    # Wait for Streamlit to be ready
    time.sleep(4)
    if proc.poll() is not None:
        print_step("✗", "Streamlit failed to start!", C.RED)
        sys.exit(1)

    print_step("✓", f"Dashboard running on http://localhost:{port}", C.GREEN)
    return proc


def start_ngrok(port: int = 8501) -> str:
    """Create an ngrok tunnel and return the public URL."""
    print_step("🌐", "Creating ngrok public tunnel...", C.CYAN)

    authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip()
    if not authtoken:
        print_step("✗", "NGROK_AUTHTOKEN not set in .env file!", C.RED)
        print(f"  {C.YELLOW}     Get your free token at: https://dashboard.ngrok.com/get-started/your-authtoken{C.RESET}")
        print(f"  {C.YELLOW}     Then add it to your .env file:{C.RESET}")
        print(f"  {C.YELLOW}     NGROK_AUTHTOKEN=your_token_here{C.RESET}")
        sys.exit(1)

    try:
        from pyngrok import ngrok, conf

        # Configure ngrok
        conf.get_default().auth_token = authtoken
        conf.get_default().region = os.getenv("NGROK_REGION", "in")  # India region

        # Set custom domain if provided
        custom_domain = os.getenv("NGROK_DOMAIN", "").strip()

        global ngrok_tunnel
        if custom_domain:
            ngrok_tunnel = ngrok.connect(port, domain=custom_domain)
        else:
            ngrok_tunnel = ngrok.connect(port)

        public_url = ngrok_tunnel.public_url
        print_step("✓", f"Ngrok tunnel active!", C.GREEN)
        return public_url

    except Exception as e:
        print_step("✗", f"Ngrok error: {e}", C.RED)
        print(f"  {C.YELLOW}     Make sure your NGROK_AUTHTOKEN is correct in .env{C.RESET}")
        sys.exit(1)


def start_monitoring():
    """Launch the AI monitoring engine (main.py --headless)."""
    print_step("🤖", "Starting AI Monitoring Engine...", C.CYAN)

    main_path = str(ROOT / "main.py")
    proc = subprocess.Popen(
        [PYTHON, main_path, "--headless"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    processes.append(proc)

    time.sleep(2)
    if proc.poll() is not None:
        print_step("⚠", "Monitoring engine exited (camera may not be available)", C.YELLOW)
        print(f"  {C.DIM}     You can start it manually later from the dashboard.{C.RESET}")
    else:
        print_step("✓", "AI monitoring engine active (camera feed processing)", C.GREEN)


def main():
    parser = argparse.ArgumentParser(description="HALO — One-Click Launcher")
    parser.add_argument("--monitor", action="store_true",
                        help="Also start the AI camera monitoring engine")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't auto-open the browser")
    parser.add_argument("--port", type=int, default=int(os.getenv("STREAMLIT_PORT", "8501")),
                        help="Streamlit port (default: 8501)")
    args = parser.parse_args()

    # Register cleanup handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Print logo
    print(LOGO)
    print_divider()

    # Step 1: Start Streamlit
    start_streamlit()

    # Step 2: Start ngrok tunnel
    public_url = start_ngrok(port=args.port)

    # Step 3: Optionally start monitoring
    if args.monitor:
        start_monitoring()

    print_divider()

    # Display the results
    print(f"""
  {C.BOLD}{C.GREEN}╔═══════════════════════════════════════════════════════╗
  ║                 🎉  HALO IS LIVE!  🎉                ║
  ╚═══════════════════════════════════════════════════════╝{C.RESET}

  {C.BOLD}🌍  Public URL:{C.RESET}   {C.CYAN}{C.BOLD}{public_url}{C.RESET}
  {C.BOLD}🖥️  Local URL:{C.RESET}    {C.DIM}http://localhost:{args.port}{C.RESET}
  {C.BOLD}🤖  AI Monitor:{C.RESET}   {C.GREEN + "Active" + C.RESET if args.monitor else C.YELLOW + "Not started (use --monitor flag or start from dashboard)" + C.RESET}

  {C.DIM}Share the public URL with anyone to access your dashboard!
  Press Ctrl+C to stop all services.{C.RESET}
""")

    # Auto-open browser
    if not args.no_browser:
        try:
            webbrowser.open(public_url)
        except Exception:
            pass

    # Keep alive — monitor subprocess health
    try:
        while True:
            time.sleep(5)

            # Check if Streamlit is still running
            for proc in processes:
                if proc.poll() is not None:
                    processes.remove(proc)

            if not processes:
                print(f"\n  {C.RED}All services have stopped. Exiting...{C.RESET}")
                cleanup()
                break

    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
