"""
Spotify Now Playing OBS Overlay - Desktop Launcher
Opens the customizer panel as a native standalone desktop window
using pywebview (no browser, no address bar, no tabs).
Falls back gracefully to default browser / Edge app mode if native window cannot be initialized.
"""

import sys
import os
import time
import threading
import urllib.request
import webbrowser

import uvicorn


PORT = 8888
CUSTOMIZER_URL = f"http://localhost:{PORT}/customizer"


def wait_for_server(timeout: int = 15) -> bool:
    """Poll until the FastAPI server is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def run_server():
    """Run the FastAPI server in a daemon thread."""
    from server import app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


def open_browser_fallback():
    """Fallback if pywebview fails: open customizer in browser."""
    print("[*] Opening customizer panel in browser...")
    webbrowser.open(CUSTOMIZER_URL)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    # ── 1. Start server in background thread ──────────────────────────────────
    srv_thread = threading.Thread(target=run_server, daemon=True, name="OBSServer")
    srv_thread.start()

    print("[*] Starting Spotify OBS Overlay Server...")
    if not wait_for_server(timeout=20):
        print("[!] Server did not respond to status check — continuing anyway.")

    print(f"[*] OBS Browser Source URL : http://localhost:{PORT}/overlay")
    print(f"[*] Control Panel URL      : {CUSTOMIZER_URL}")
    print("[*] Opening Control Panel desktop window...")

    # ── 2. Open native desktop window via pywebview (with fallback) ───────────
    try:
        import webview
        window = webview.create_window(
            title="🎵 Spotify OBS Overlay — Control Panel",
            url=CUSTOMIZER_URL,
            width=1300,
            height=870,
            min_size=(900, 600),
            resizable=True,
            background_color="#0d1117",
            js_api=None,
        )
        webview.start(debug=False)
        print("[*] Window closed. Server stopped.")
        sys.exit(0)
    except Exception as err:
        print(f"[!] Native desktop window error: {err}")
        open_browser_fallback()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
