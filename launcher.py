"""
Spotify Now Playing OBS Overlay - Desktop Launcher
Opens the customizer panel as a native standalone desktop window
using pywebview (no browser, no address bar, no tabs).
"""

import sys
import os
import time
import threading
import urllib.request

import uvicorn
import webview


# ── Port ──────────────────────────────────────────────────────────────────────
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
    # Import here so it runs in this thread's context
    from server import app  # noqa: F401 – registers all routes
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
        access_log=False,
    )


def main():
    # ── 1. Start server in background thread ──────────────────────────────────
    srv_thread = threading.Thread(target=run_server, daemon=True, name="OBSServer")
    srv_thread.start()

    print("[*] Starting Spotify OBS Overlay Server…")
    if not wait_for_server(timeout=20):
        print("[!] Server did not start in time — opening window anyway.")

    print(f"[*] OBS Browser Source URL : http://localhost:{PORT}/overlay")
    print(f"[*] Opening customizer panel…")

    # ── 2. Open native desktop window via pywebview ───────────────────────────
    window = webview.create_window(
        title="🎵 Spotify OBS Overlay — Control Panel",
        url=CUSTOMIZER_URL,
        width=1300,
        height=870,
        min_size=(900, 600),
        resizable=True,
        # Transparent background keeps the dark card look crisp
        background_color="#0d1117",
        # Allow JavaScript (required for live preview and WebSocket)
        js_api=None,
    )

    # Start the webview — this call BLOCKS until the window is closed
    webview.start(debug=False)

    print("[*] Window closed. Server will stop.")
    sys.exit(0)


if __name__ == "__main__":
    # Ensure we run from the project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
