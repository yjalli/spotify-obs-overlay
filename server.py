import asyncio
import base64
from contextlib import asynccontextmanager
import copy
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SpotifyOverlay")

# Windows Media Control (WinRT / WinSDK) imports
WINSDK_AVAILABLE = False
try:
    # 1. Modern official winrt (supports Python 3.9, 3.10, 3.11, 3.12, 3.13+)
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSession as MediaSession,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winrt.windows.storage.streams import DataReader
    WINSDK_AVAILABLE = True
    logger.info('Using modern winrt package for Windows Media Controls.')
except ImportError:
    try:
        # 2. Legacy winsdk fallback (supports Python 3.10 - 3.12)
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSession as MediaSession,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
        from winsdk.windows.storage.streams import DataReader
        WINSDK_AVAILABLE = True
        logger.info('Using winsdk package for Windows Media Controls.')
    except ImportError:
        WINSDK_AVAILABLE = False
        logger.warning('Neither winrt nor winsdk found. Windows Media Control integration will be limited.')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "theme": "purple-dusk",
    "chassisStyle": "capsule",
    "orientation": "horizontal",
    "position": "bottom-left",
    "offsetX": 40,
    "offsetY": 40,
    "scale": 100,
    "cardWidth": 520,
    "cardPadding": 14,
    "gap": 16,
    "bgType": "glass",
    "bgColor": "#181226",
    "bgGradient1": "#1a102a",
    "bgGradient2": "#0c0816",
    "bgGradientAngle": 180,
    "bgOpacity": 92,
    "backdropBlur": 20,
    "cardRadius": 28,
    "borderWidth": 2,
    "borderColor": "rgba(168, 85, 247, 0.75)",
    "cardShadow": "0 0 25px rgba(168, 85, 247, 0.45), inset 0 0 14px rgba(168, 85, 247, 0.2)",
    "albumSize": 80,
    "albumShape": "rounded",
    "albumRadius": 18,
    "albumSpin": False,
    "albumShadow": True,
    "albumBorderWidth": 2,
    "albumBorderColor": "rgba(192, 132, 252, 0.8)",
    "albumProtrude": False,
    "titleFont": "Inter",
    "titleSize": 18,
    "titleWeight": "700",
    "titleColor": "#ffffff",
    "titleItalic": False,
    "titleTransform": "none",
    "titleMarquee": True,
    "titleShadow": True,
    "artistFont": "Inter",
    "artistSize": 14,
    "artistWeight": "500",
    "artistColor": "#c4b5fd",
    "artistItalic": False,
    "artistTransform": "none",
    "showSpotifyIcon": True,
    "spotifyIconColor": "#a855f7",
    "showAlbum": False,
    "albumFontSize": 12,
    "albumFontColor": "#777777",
    "showProgress": True,
    "progressHeight": 6,
    "progressRadius": 3,
    "progressTrackColor": "rgba(255, 255, 255, 0.16)",
    "progressFillColor": "#a855f7",
    "progressFillGradient": True,
    "progressFillColor2": "#c084fc",
    "progressGlow": True,
    "showProgressThumb": True,
    "thumbColor": "#ffffff",
    "showTimestamps": True,
    "timestampFont": "Inter",
    "timestampSize": 11,
    "timestampColor": "#e2e8f0",
    "showEqualizer": True,
    "equalizerColor": "#a855f7",
    # Audio Rhythm Waveform Visualizer (Image 2)
    "showRhythmWave": True,
    "rhythmColor": "#a855f7",
    "rhythmHeight": 36,
    "rhythmGlow": True,
    "accentStripes": False,
    "showPauseIcon": True,
    "dimWhenPaused": True,
    "dimOpacity": 70,
    "autoHideInactive": False,
    "autoHidePaused": False,
    "autoHideDelay": 10,
    "transitionEffect": "slide-up",
    "testMode": False
}

# 12 Theme presets with individual rhythm wave colors
PRESETS = {
    # 1. Purple Dusk Capsule (Reference Image 1)
    "purple-dusk": {
        "name": "Purple Dusk Capsule",
        "config": {
            "chassisStyle": "capsule",
            "cardRadius": 28,
            "bgType": "glass",
            "bgColor": "#181226",
            "bgOpacity": 92,
            "backdropBlur": 20,
            "borderWidth": 2,
            "borderColor": "rgba(168, 85, 247, 0.75)",
            "cardShadow": "0 0 25px rgba(168, 85, 247, 0.45), inset 0 0 14px rgba(168, 85, 247, 0.2)",
            "albumShape": "rounded",
            "albumRadius": 18,
            "albumBorderWidth": 2,
            "albumBorderColor": "rgba(192, 132, 252, 0.8)",
            "albumProtrude": False,
            "titleFont": "Inter",
            "titleColor": "#ffffff",
            "titleItalic": False,
            "artistColor": "#c4b5fd",
            "artistItalic": False,
            "showSpotifyIcon": False,
            "showEqualizer": True,
            "equalizerColor": "#a855f7",
            "showRhythmWave": True,
            "rhythmColor": "#a855f7",
            "rhythmGlow": True,
            "accentStripes": False,
            "progressFillColor": "#a855f7",
            "progressFillGradient": True,
            "progressFillColor2": "#c084fc",
            "progressTrackColor": "rgba(255, 255, 255, 0.16)",
            "showProgressThumb": True,
            "thumbColor": "#ffffff",
            "progressGlow": True,
            "timestampColor": "#e2e8f0"
        }
    },
    # 2. Synthwave Horizon (Reference Image 2)
    "synthwave-horizon": {
        "name": "Synthwave Horizon",
        "config": {
            "chassisStyle": "horizon",
            "cardRadius": 14,
            "bgType": "gradient",
            "bgGradient1": "#1a0c24",
            "bgGradient2": "#0e0517",
            "bgGradientAngle": 90,
            "bgOpacity": 95,
            "backdropBlur": 16,
            "borderWidth": 2,
            "borderColor": "#ff4500",
            "cardShadow": "0 0 25px rgba(255, 69, 0, 0.4), 0 0 12px rgba(255, 0, 127, 0.4)",
            "albumShape": "rounded",
            "albumRadius": 14,
            "albumBorderWidth": 2.5,
            "albumBorderColor": "#ff5500",
            "albumProtrude": True,
            "titleFont": "Montserrat",
            "titleColor": "#ffffff",
            "titleItalic": True,
            "artistColor": "#ff7700",
            "artistItalic": True,
            "showSpotifyIcon": False,
            "showEqualizer": False,
            "showRhythmWave": True,
            "rhythmColor": "#ff007f",
            "rhythmGlow": True,
            "accentStripes": True,
            "progressFillColor": "#ffaa00",
            "progressFillGradient": True,
            "progressFillColor2": "#ff007f",
            "progressTrackColor": "rgba(255, 255, 255, 0.12)",
            "showProgressThumb": True,
            "thumbColor": "#ff007f",
            "progressGlow": True,
            "timestampColor": "#ffffff"
        }
    },
    # 3. Frosted Clean Glass (Reference Image 3 & Image 2 visualizer)
    "frosted-clean": {
        "name": "Frosted Clean Glass",
        "config": {
            "chassisStyle": "frosted-light",
            "cardRadius": 22,
            "bgType": "glass",
            "bgColor": "#ffffff",
            "bgOpacity": 92,
            "backdropBlur": 24,
            "borderWidth": 1,
            "borderColor": "rgba(255, 255, 255, 0.8)",
            "cardShadow": "0 12px 35px rgba(0, 0, 0, 0.18), 0 2px 6px rgba(0, 0, 0, 0.08)",
            "albumShape": "rounded",
            "albumRadius": 16,
            "albumBorderWidth": 2.5,
            "albumBorderColor": "#1db954",
            "albumProtrude": True,
            "titleFont": "Inter",
            "titleColor": "#0f172a",
            "titleItalic": False,
            "artistColor": "#64748b",
            "artistItalic": False,
            "showSpotifyIcon": True,
            "spotifyIconColor": "#1db954",
            "showEqualizer": False,
            "showRhythmWave": True,
            "rhythmColor": "#1db954",
            "rhythmGlow": True,
            "accentStripes": False,
            "progressFillColor": "#1db954",
            "progressFillGradient": False,
            "progressTrackColor": "rgba(0, 0, 0, 0.12)",
            "showProgressThumb": True,
            "thumbColor": "#1db954",
            "progressGlow": True,
            "timestampColor": "#64748b"
        }
    },
    # 4. Cyberpunk Mecha HUD (Reference Image 4)
    "mecha-hud": {
        "name": "Cyberpunk Mecha HUD",
        "config": {
            "chassisStyle": "mecha-hud",
            "cardRadius": 8,
            "bgType": "gradient",
            "bgGradient1": "#0d1117",
            "bgGradient2": "#140a1c",
            "bgGradientAngle": 135,
            "bgOpacity": 94,
            "backdropBlur": 16,
            "borderWidth": 2,
            "borderColor": "#00f0ff",
            "cardShadow": "0 0 28px rgba(0, 240, 255, 0.4), 0 0 14px rgba(255, 0, 127, 0.4)",
            "albumShape": "rounded",
            "albumRadius": 8,
            "albumBorderWidth": 2,
            "albumBorderColor": "#00f0ff",
            "albumProtrude": False,
            "titleFont": "Outfit",
            "titleColor": "#ffffff",
            "titleItalic": False,
            "artistColor": "#94a3b8",
            "artistItalic": False,
            "showSpotifyIcon": True,
            "spotifyIconColor": "#00f0ff",
            "showEqualizer": False,
            "showRhythmWave": True,
            "rhythmColor": "#00f0ff",
            "rhythmGlow": True,
            "accentStripes": True,
            "progressFillColor": "#00f0ff",
            "progressFillGradient": True,
            "progressFillColor2": "#ff007f",
            "progressTrackColor": "rgba(255, 255, 255, 0.15)",
            "showProgressThumb": True,
            "thumbColor": "#ffffff",
            "progressGlow": True,
            "timestampColor": "#ffffff"
        }
    },
    # 5. Spotify Glass Classic
    "spotify-glass": {
        "name": "Spotify Glass Classic",
        "config": {
            "chassisStyle": "standard",
            "cardRadius": 16,
            "bgType": "glass",
            "bgColor": "#121212",
            "bgOpacity": 82,
            "backdropBlur": 16,
            "borderWidth": 1,
            "borderColor": "rgba(255, 255, 255, 0.12)",
            "cardShadow": "0 12px 32px rgba(0, 0, 0, 0.5)",
            "albumShape": "rounded",
            "albumRadius": 12,
            "albumBorderWidth": 0,
            "albumProtrude": False,
            "titleFont": "Inter",
            "titleColor": "#ffffff",
            "titleItalic": False,
            "artistColor": "#b3b3b3",
            "artistItalic": False,
            "showSpotifyIcon": False,
            "showEqualizer": True,
            "equalizerColor": "#1db954",
            "showRhythmWave": True,
            "rhythmColor": "#1db954",
            "rhythmGlow": True,
            "accentStripes": False,
            "progressFillColor": "#1db954",
            "progressFillGradient": False,
            "progressTrackColor": "rgba(255, 255, 255, 0.15)",
            "showProgressThumb": False,
            "progressGlow": True,
            "timestampColor": "#999999"
        }
    },
    # 6. Spotify High-Voltage Neon
    "spotify-neon": {
        "name": "Spotify High-Voltage Neon",
        "config": {
            "chassisStyle": "standard",
            "cardRadius": 12,
            "bgType": "solid",
            "bgColor": "#0b0e0c",
            "bgOpacity": 96,
            "backdropBlur": 0,
            "borderWidth": 2,
            "borderColor": "#1db954",
            "cardShadow": "0 0 25px rgba(29, 185, 84, 0.45)",
            "albumShape": "rounded",
            "albumRadius": 10,
            "albumBorderWidth": 2,
            "albumBorderColor": "#1db954",
            "albumProtrude": False,
            "titleFont": "Montserrat",
            "titleColor": "#ffffff",
            "titleItalic": False,
            "artistColor": "#1db954",
            "artistItalic": False,
            "showSpotifyIcon": True,
            "spotifyIconColor": "#1db954",
            "showEqualizer": True,
            "equalizerColor": "#1db954",
            "showRhythmWave": True,
            "rhythmColor": "#1db954",
            "rhythmGlow": True,
            "accentStripes": False,
            "progressFillColor": "#1db954",
            "progressFillGradient": True,
            "progressFillColor2": "#1ed760",
            "progressTrackColor": "rgba(29, 185, 84, 0.2)",
            "showProgressThumb": True,
            "thumbColor": "#1ed760",
            "progressGlow": True,
            "timestampColor": "#1db954"
        }
    },
    # 7. Retro Vinyl Record
    "retro-vinyl": {
        "name": "Retro Vinyl Record",
        "config": {
            "chassisStyle": "standard",
            "cardRadius": 20,
            "bgType": "glass",
            "bgColor": "#1a1614",
            "bgOpacity": 88,
            "backdropBlur": 12,
            "borderWidth": 1,
            "borderColor": "rgba(240, 190, 130, 0.25)",
            "cardShadow": "0 10px 30px rgba(0, 0, 0, 0.6)",
            "albumShape": "vinyl",
            "albumRadius": 50,
            "albumSpin": True,
            "albumBorderWidth": 0,
            "albumProtrude": False,
            "titleFont": "Playfair Display",
            "titleColor": "#fdfbf7",
            "titleItalic": False,
            "artistColor": "#e0b888",
            "artistItalic": False,
            "showSpotifyIcon": False,
            "showEqualizer": True,
            "equalizerColor": "#e0a050",
            "showRhythmWave": True,
            "rhythmColor": "#e0a050",
            "rhythmGlow": False,
            "accentStripes": False,
            "progressFillColor": "#e0a050",
            "progressFillGradient": True,
            "progressFillColor2": "#ffcc77",
            "progressTrackColor": "rgba(255, 255, 255, 0.12)",
            "showProgressThumb": False,
            "progressGlow": False,
            "timestampColor": "#e0b888"
        }
    },
    # 8. Pure Floating Minimal
    "clean-floating": {
        "name": "Pure Floating Minimal",
        "config": {
            "chassisStyle": "standard",
            "bgType": "transparent",
            "bgColor": "transparent",
            "bgOpacity": 0,
            "backdropBlur": 0,
            "cardRadius": 0,
            "borderWidth": 0,
            "borderColor": "transparent",
            "cardShadow": "none",
            "albumShape": "rounded",
            "albumRadius": 12,
            "albumBorderWidth": 0,
            "albumProtrude": False,
            "titleFont": "Inter",
            "titleColor": "#ffffff",
            "titleShadow": True,
            "artistColor": "#cccccc",
            "showSpotifyIcon": False,
            "showEqualizer": True,
            "equalizerColor": "#ffffff",
            "showRhythmWave": True,
            "rhythmColor": "#ffffff",
            "rhythmGlow": True,
            "accentStripes": False,
            "progressFillColor": "#ffffff",
            "progressFillGradient": False,
            "progressTrackColor": "rgba(255, 255, 255, 0.25)",
            "showProgressThumb": True,
            "thumbColor": "#ffffff",
            "progressGlow": True,
            "timestampColor": "#ffffff"
        }
    },
    # 9. Compact Streamer Pill
    "compact-pill": {
        "name": "Compact Streamer Pill",
        "config": {
            "chassisStyle": "capsule",
            "orientation": "compact",
            "cardWidth": 390,
            "cardPadding": 10,
            "albumSize": 52,
            "bgType": "glass",
            "bgColor": "#000000",
            "bgOpacity": 85,
            "backdropBlur": 20,
            "cardRadius": 32,
            "borderWidth": 1,
            "borderColor": "rgba(255, 255, 255, 0.18)",
            "cardShadow": "0 8px 24px rgba(0, 0, 0, 0.5)",
            "albumShape": "circle",
            "albumRadius": 50,
            "albumProtrude": False,
            "titleFont": "Inter",
            "titleSize": 15,
            "artistSize": 12,
            "titleColor": "#ffffff",
            "artistColor": "#1db954",
            "showSpotifyIcon": False,
            "progressFillColor": "#1db954",
            "progressHeight": 3,
            "showProgressThumb": False,
            "showAlbum": False,
            "showTimestamps": True,
            "showRhythmWave": False,
            "equalizerColor": "#1db954"
        }
    },
    # 10. Nord Arctic Frost
    "nord-frost": {
        "name": "Nord Arctic Frost",
        "config": {
            "chassisStyle": "standard",
            "cardRadius": 14,
            "bgType": "glass",
            "bgColor": "#2e3440",
            "bgOpacity": 88,
            "backdropBlur": 16,
            "borderWidth": 1,
            "borderColor": "rgba(136, 192, 208, 0.3)",
            "cardShadow": "0 10px 28px rgba(10, 15, 25, 0.4)",
            "albumShape": "rounded",
            "albumRadius": 10,
            "albumBorderWidth": 1,
            "albumBorderColor": "#88c0d0",
            "albumProtrude": False,
            "titleFont": "Fira Code",
            "titleColor": "#eceff4",
            "artistColor": "#88c0d0",
            "showSpotifyIcon": True,
            "spotifyIconColor": "#88c0d0",
            "progressFillColor": "#81a1c1",
            "progressFillGradient": True,
            "progressFillColor2": "#88c0d0",
            "progressTrackColor": "rgba(236, 239, 244, 0.15)",
            "showProgressThumb": True,
            "thumbColor": "#88c0d0",
            "equalizerColor": "#88c0d0",
            "showRhythmWave": True,
            "rhythmColor": "#88c0d0",
            "rhythmGlow": True,
            "progressGlow": True,
            "timestampColor": "#d8dee9"
        }
    },
    # 11. Crimson Blade / Bloodmoon
    "crimson-blade": {
        "name": "Crimson Blade / Bloodmoon",
        "config": {
            "chassisStyle": "mecha-hud",
            "cardRadius": 6,
            "bgType": "gradient",
            "bgGradient1": "#1a0808",
            "bgGradient2": "#0a0303",
            "bgGradientAngle": 135,
            "bgOpacity": 95,
            "backdropBlur": 12,
            "borderWidth": 2,
            "borderColor": "#ef4444",
            "cardShadow": "0 0 25px rgba(239, 68, 68, 0.45)",
            "albumShape": "rounded",
            "albumRadius": 6,
            "albumBorderWidth": 2,
            "albumBorderColor": "#ef4444",
            "albumProtrude": False,
            "titleFont": "Oswald",
            "titleColor": "#ffffff",
            "artistColor": "#f87171",
            "showSpotifyIcon": False,
            "accentStripes": True,
            "progressFillColor": "#dc2626",
            "progressFillGradient": True,
            "progressFillColor2": "#f87171",
            "progressTrackColor": "rgba(255, 255, 255, 0.15)",
            "showProgressThumb": True,
            "thumbColor": "#ef4444",
            "equalizerColor": "#ef4444",
            "showRhythmWave": True,
            "rhythmColor": "#ef4444",
            "rhythmGlow": True,
            "progressGlow": True,
            "timestampColor": "#fca5a5"
        }
    },
    # 12. Deep Space Nebula
    "deep-space": {
        "name": "Deep Space Nebula",
        "config": {
            "chassisStyle": "capsule",
            "cardRadius": 28,
            "bgType": "gradient",
            "bgGradient1": "#091026",
            "bgGradient2": "#130924",
            "bgGradientAngle": 135,
            "bgOpacity": 90,
            "backdropBlur": 20,
            "borderWidth": 2,
            "borderColor": "rgba(56, 189, 248, 0.7)",
            "cardShadow": "0 0 25px rgba(56, 189, 248, 0.35), 0 0 10px rgba(168, 85, 247, 0.3)",
            "albumShape": "circle",
            "albumRadius": 50,
            "albumBorderWidth": 2,
            "albumBorderColor": "#38bdf8",
            "albumProtrude": False,
            "titleFont": "Poppins",
            "titleColor": "#ffffff",
            "artistColor": "#38bdf8",
            "showSpotifyIcon": True,
            "spotifyIconColor": "#38bdf8",
            "showRhythmWave": True,
            "rhythmColor": "#38bdf8",
            "rhythmGlow": True,
            "progressFillColor": "#38bdf8",
            "progressFillGradient": True,
            "progressFillColor2": "#a855f7",
            "progressTrackColor": "rgba(255, 255, 255, 0.15)",
            "showProgressThumb": True,
            "thumbColor": "#ffffff",
            "equalizerColor": "#38bdf8",
            "progressGlow": True,
            "timestampColor": "#bae6fd"
        }
    }
}

# Load or initialize config
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = copy.deepcopy(DEFAULT_CONFIG)
                config.update(data)
                return config
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")
    save_config(DEFAULT_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)

def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving config.json: {e}")

CURRENT_CONFIG = load_config()

# Global State for track
DEFAULT_ARTWORK_SVG = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%23181818'/><circle cx='50' cy='50' r='38' fill='%23121212'/><circle cx='50' cy='50' r='12' fill='%231db954'/><path d='M32 40 A24 24 0 0 1 68 40' stroke='%231db954' stroke-width='4' fill='none' stroke-linecap='round'/><path d='M36 50 A18 18 0 0 1 64 50' stroke='%231db954' stroke-width='3.5' fill='none' stroke-linecap='round'/><path d='M40 60 A12 12 0 0 1 60 60' stroke='%231db954' stroke-width='3' fill='none' stroke-linecap='round'/></svg>"

current_track_state = {
    "title": "Waiting for Spotify...",
    "artist": "No track detected",
    "album": "",
    "duration": 0,
    "position": 0,
    "status": "STOPPED",
    "is_playing": False,
    "artwork": DEFAULT_ARTWORK_SVG,
    "app_id": "",
    "timestamp": time.time(),
    "has_track": False
}

cached_track_id = ""
cached_artwork = DEFAULT_ARTWORK_SVG

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")
        await websocket.send_json({"type": "config_update", "data": CURRENT_CONFIG})
        await websocket.send_json({"type": "track_update", "data": current_track_state})

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, message: dict):
        if not self.active_connections:
            return
        dead = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.active_connections.discard(d)

manager = ConnectionManager()

# Mock track generator for Test Mode
MOCK_TRACKS = [
    {
        "title": "After Hours",
        "artist": "The Weeknd",
        "album": "After Hours",
        "duration": 268,
        "artwork": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80"
    },
    {
        "title": "Blinding Lights",
        "artist": "The Weeknd",
        "album": "After Hours",
        "duration": 200,
        "artwork": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=400&q=80"
    },
    {
        "title": "Starboy (feat. Daft Punk)",
        "artist": "The Weeknd, Daft Punk",
        "album": "Starboy",
        "duration": 230,
        "artwork": "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=400&q=80"
    },
    {
        "title": "Midnight City - Extended Synth",
        "artist": "M83",
        "album": "Hurry Up, We're Dreaming",
        "duration": 244,
        "artwork": "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=400&q=80"
    }
]
mock_idx = 0
mock_start_time = time.time()

# Background Worker for Media Detection
async def media_tracker_loop():
    global current_track_state, cached_track_id, cached_artwork, mock_idx, mock_start_time
    logger.info("Starting Media Tracker background worker...")

    media_manager = None
    if WINSDK_AVAILABLE:
        try:
            media_manager = await MediaManager.request_async()
            logger.info("Windows Media Transport Controls Session Manager initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize MediaManager: {e}")

    while True:
        try:
            if CURRENT_CONFIG.get("testMode", False):
                now = time.time()
                mock = MOCK_TRACKS[mock_idx % len(MOCK_TRACKS)]
                elapsed = int(now - mock_start_time) % mock["duration"]
                mock_state = {
                    "title": mock["title"],
                    "artist": mock["artist"],
                    "album": mock["album"],
                    "duration": mock["duration"],
                    "position": elapsed,
                    "status": "PLAYING",
                    "is_playing": True,
                    "artwork": mock["artwork"],
                    "app_id": "Spotify.exe (Mock)",
                    "timestamp": now,
                    "has_track": True
                }
                current_track_state = mock_state
                await manager.broadcast_json({"type": "track_update", "data": mock_state})
                await asyncio.sleep(1)
                continue

            if not WINSDK_AVAILABLE:
                await asyncio.sleep(2)
                continue

            if not media_manager:
                try:
                    media_manager = await MediaManager.request_async()
                except Exception:
                    await asyncio.sleep(2)
                    continue

            target_session = None
            try:
                sessions = media_manager.get_sessions()
            except Exception:
                sessions = []

            for s in sessions:
                try:
                    app_id = s.source_app_user_model_id.lower()
                    if "spotify" in app_id:
                        target_session = s
                        break
                except Exception:
                    pass

            if not target_session:
                try:
                    target_session = media_manager.get_current_session()
                except Exception:
                    target_session = None

            if not target_session and len(sessions) > 0:
                target_session = sessions[0]

            if not target_session:
                if current_track_state["has_track"]:
                    current_track_state = {
                        "title": "Waiting for Spotify...",
                        "artist": "No active playback",
                        "album": "",
                        "duration": 0,
                        "position": 0,
                        "status": "STOPPED",
                        "is_playing": False,
                        "artwork": DEFAULT_ARTWORK_SVG,
                        "app_id": "",
                        "timestamp": time.time(),
                        "has_track": False
                    }
                    cached_track_id = ""
                    await manager.broadcast_json({"type": "track_update", "data": current_track_state})
                await asyncio.sleep(1)
                continue

            app_id = target_session.source_app_user_model_id
            playback_info = target_session.get_playback_info()
            status_str = playback_info.playback_status.name if playback_info else "Unknown"
            is_playing = (status_str == "PLAYING")

            media_props = await target_session.try_get_media_properties_async()
            title = (media_props.title if media_props and media_props.title else "").strip()
            artist = (media_props.artist if media_props and media_props.artist else "").strip()
            album = (media_props.album_title if media_props and media_props.album_title else "").strip()

            timeline = target_session.get_timeline_properties()
            position = 0.0
            duration = 0.0
            if timeline:
                if timeline.position:
                    position = timeline.position.total_seconds()
                if timeline.end_time:
                    duration = timeline.end_time.total_seconds()

            if not title and not artist:
                if current_track_state["has_track"]:
                    current_track_state = {
                        "title": "Spotify Idle",
                        "artist": "Play a track in Spotify",
                        "album": "",
                        "duration": 0,
                        "position": 0,
                        "status": status_str,
                        "is_playing": is_playing,
                        "artwork": DEFAULT_ARTWORK_SVG,
                        "app_id": app_id,
                        "timestamp": time.time(),
                        "has_track": False
                    }
                    await manager.broadcast_json({"type": "track_update", "data": current_track_state})
                await asyncio.sleep(1)
                continue

            track_id = f"{app_id}|{title}|{artist}|{album}"

            if track_id != cached_track_id:
                cached_track_id = track_id
                cached_artwork = DEFAULT_ARTWORK_SVG
                if media_props and media_props.thumbnail:
                    try:
                        stream = await media_props.thumbnail.open_read_async()
                        size = stream.size
                        if size > 0:
                            reader = DataReader(stream)
                            await reader.load_async(size)
                            buf = bytearray(size)
                            reader.read_bytes(buf)
                            b64 = base64.b64encode(buf).decode("ascii")
                            cached_artwork = f"data:image/jpeg;base64,{b64}"
                    except Exception as err:
                        logger.warning(f"Could not load thumbnail stream: {err}")

            new_state = {
                "title": title,
                "artist": artist,
                "album": album,
                "duration": duration,
                "position": position,
                "status": status_str,
                "is_playing": is_playing,
                "artwork": cached_artwork,
                "app_id": app_id,
                "timestamp": time.time(),
                "has_track": True
            }

            diff = (
                new_state["title"] != current_track_state["title"]
                or new_state["artist"] != current_track_state["artist"]
                or new_state["status"] != current_track_state["status"]
                or abs(new_state["position"] - current_track_state["position"]) > 1.8
                or abs(new_state["duration"] - current_track_state["duration"]) > 0.5
                or new_state["has_track"] != current_track_state["has_track"]
            )

            current_track_state = new_state
            if diff:
                await manager.broadcast_json({"type": "track_update", "data": current_track_state})

            await asyncio.sleep(0.7)

        except Exception as e:
            logger.error(f"Error in media tracker loop: {e}")
            await asyncio.sleep(1.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(media_tracker_loop())
    yield
    task.cancel()

# FastAPI App setup
app = FastAPI(title="Spotify OBS Overlay", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/customizer")

@app.get("/overlay")
async def get_overlay():
    overlay_path = os.path.join(STATIC_DIR, "overlay.html")
    if os.path.exists(overlay_path):
        return FileResponse(overlay_path, media_type="text/html")
    return HTMLResponse("<h1>Overlay page not found in static folder</h1>", status_code=404)

@app.get("/customizer")
async def get_customizer():
    customizer_path = os.path.join(STATIC_DIR, "customizer.html")
    if os.path.exists(customizer_path):
        return FileResponse(customizer_path, media_type="text/html")
    return HTMLResponse("<h1>Customizer page not found in static folder</h1>", status_code=404)

@app.get("/api/status")
async def get_status():
    return {
        "winsdk_available": WINSDK_AVAILABLE,
        "track": current_track_state,
        "connected_clients": len(manager.active_connections),
        "test_mode": CURRENT_CONFIG.get("testMode", False)
    }

@app.get("/api/config")
async def get_config():
    return CURRENT_CONFIG

@app.post("/api/config")
async def update_config(new_config: dict):
    global CURRENT_CONFIG
    CURRENT_CONFIG.update(new_config)
    save_config(CURRENT_CONFIG)
    await manager.broadcast_json({"type": "config_update", "data": CURRENT_CONFIG})
    return {"status": "ok", "config": CURRENT_CONFIG}

@app.get("/api/presets")
async def get_presets():
    return PRESETS

@app.post("/api/presets/{preset_key}")
async def apply_preset(preset_key: str):
    global CURRENT_CONFIG
    if preset_key not in PRESETS:
        return JSONResponse(status_code=404, content={"error": "Preset not found"})
    preset_data = PRESETS[preset_key]["config"]
    CURRENT_CONFIG.update(preset_data)
    CURRENT_CONFIG["theme"] = preset_key
    save_config(CURRENT_CONFIG)
    await manager.broadcast_json({"type": "config_update", "data": CURRENT_CONFIG})
    return {"status": "ok", "theme": preset_key, "config": CURRENT_CONFIG}

@app.post("/api/reset-config")
async def reset_config():
    global CURRENT_CONFIG
    CURRENT_CONFIG = copy.deepcopy(DEFAULT_CONFIG)
    save_config(CURRENT_CONFIG)
    await manager.broadcast_json({"type": "config_update", "data": CURRENT_CONFIG})
    return {"status": "ok", "config": CURRENT_CONFIG}

@app.post("/api/test-mode")
async def toggle_test_mode(payload: dict):
    global CURRENT_CONFIG, mock_start_time, mock_idx
    enabled = payload.get("enabled", not CURRENT_CONFIG.get("testMode", False))
    CURRENT_CONFIG["testMode"] = enabled
    if payload.get("nextTrack", False):
        mock_idx += 1
        mock_start_time = time.time()
    save_config(CURRENT_CONFIG)
    await manager.broadcast_json({"type": "config_update", "data": CURRENT_CONFIG})
    return {"status": "ok", "testMode": enabled}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "live_preview_config":
                    CURRENT_CONFIG.update(msg.get("data", {}))
                    await manager.broadcast_json({"type": "config_update", "data": CURRENT_CONFIG})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    port = 8888
    logger.info(f"Starting Spotify OBS Overlay Server on http://localhost:{port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port, log_level="warning")
