/* ==========================================================
   Spotify OBS Overlay - Client Controller
   Handles WebSocket real-time sync, 60fps progress interpolation,
   dynamic CSS variables injection, and animations.
   ========================================================== */

(function () {
  'use strict';

  // DOM Elements
  const stage = document.getElementById('obs-stage');
  const card = document.getElementById('spotify-card');
  const albumContainer = document.getElementById('album-container');
  const albumWrap = document.getElementById('album-wrap');
  const albumCover = document.getElementById('album-cover');
  const mechaBrackets = document.getElementById('mecha-brackets');
  const trackTitle = document.getElementById('track-title');
  const titleScroller = document.getElementById('title-scroller');
  const trackArtist = document.getElementById('track-artist');
  const trackAlbum = document.getElementById('track-album');
  const artistSeparator = document.getElementById('artist-separator');
  const spotifyBadge = document.getElementById('spotify-badge');
  const equalizer = document.getElementById('equalizer');
  const rhythmVisualizer = document.getElementById('rhythm-visualizer');
  const progressSection = document.getElementById('progress-section');
  const progressFill = document.getElementById('progress-fill');
  const progressThumb = document.getElementById('progress-thumb');
  const timestampRow = document.getElementById('timestamp-row');
  const timeCurrent = document.getElementById('time-current');
  const timeTotal = document.getElementById('time-total');
  const pausedBadge = document.getElementById('paused-badge');
  const stripesTop = document.getElementById('stripes-top');
  const stripesBottom = document.getElementById('stripes-bottom');

  // Playback tracking state
  let currentTrack = null;
  let currentConfig = {};
  let basePosition = 0;
  let baseDuration = 0;
  let lastTimestamp = 0;
  let isPlaying = false;
  let animFrameId = null;
  let autoHideTimer = null;
  let ws = null;
  let retryCount = 0;

  // Format seconds to mm:ss
  function formatTime(totalSeconds) {
    if (isNaN(totalSeconds) || totalSeconds < 0) return '0:00';
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.floor(totalSeconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  // Smooth 60fps progress interpolation loop
  function updateProgressLoop() {
    if (isPlaying && baseDuration > 0) {
      const now = performance.now();
      const elapsedSec = (now - lastTimestamp) / 1000;
      const currentPos = Math.min(basePosition + elapsedSec, baseDuration);
      const percentage = (currentPos / baseDuration) * 100;

      progressFill.style.width = `${percentage.toFixed(2)}%`;
      timeCurrent.textContent = formatTime(currentPos);
    }
    animFrameId = requestAnimationFrame(updateProgressLoop);
  }

  // Apply track details to DOM
  function renderTrack(data) {
    currentTrack = data;
    const hasTrack = data.has_track !== false && Boolean(data.title && data.title !== 'Waiting for Spotify...');

    // Title animation on change
    if (trackTitle.textContent !== data.title) {
      trackTitle.style.opacity = '0';
      setTimeout(() => {
        trackTitle.textContent = data.title || 'Waiting for Spotify...';
        trackTitle.style.opacity = '1';
        checkMarquee();
      }, 150);
    }

    trackArtist.textContent = data.artist || 'No track detected';

    if (data.album && currentConfig.showAlbum) {
      trackAlbum.textContent = data.album;
      trackAlbum.classList.remove('hidden');
      artistSeparator.classList.remove('hidden');
    } else {
      trackAlbum.classList.add('hidden');
      artistSeparator.classList.add('hidden');
    }

    // Album Artwork
    if (data.artwork && albumCover.src !== data.artwork) {
      albumCover.style.opacity = '0.3';
      const img = new Image();
      img.onload = () => {
        albumCover.src = data.artwork;
        albumCover.style.opacity = '1';
      };
      img.onerror = () => {
        albumCover.src = data.artwork;
        albumCover.style.opacity = '1';
      };
      img.src = data.artwork;
    }

    // Playback Timing
    baseDuration = Number(data.duration) || 0;
    basePosition = Number(data.position) || 0;
    lastTimestamp = performance.now();
    isPlaying = (data.status === 'PLAYING');

    timeTotal.textContent = formatTime(baseDuration);
    timeCurrent.textContent = formatTime(basePosition);
    const initialPercent = baseDuration > 0 ? (basePosition / baseDuration) * 100 : 0;
    progressFill.style.width = `${initialPercent.toFixed(2)}%`;

    // Play/Pause State Styling
    if (isPlaying) {
      card.classList.remove('is-paused');
      if (currentConfig.albumSpin) {
        albumWrap.classList.add('spinning');
      }
    } else {
      if (currentConfig.dimWhenPaused) {
        card.classList.add('is-paused');
      }
    }

    // Auto-hide handling
    handleAutoHide(hasTrack, isPlaying);
  }

  // Auto-hide logic based on config
  function handleAutoHide(hasTrack, isPlayingNow) {
    if (autoHideTimer) {
      clearTimeout(autoHideTimer);
      autoHideTimer = null;
    }

    if (currentConfig.autoHideInactive && !hasTrack) {
      card.classList.add('hidden');
      return;
    }

    if (currentConfig.autoHidePaused && !isPlayingNow) {
      const delay = (currentConfig.autoHideDelay || 10) * 1000;
      autoHideTimer = setTimeout(() => {
        card.classList.add('hidden');
      }, delay);
      return;
    }

    card.classList.remove('hidden');
  }

  // Check if title overflows container to trigger smooth marquee
  function checkMarquee() {
    if (!currentConfig.titleMarquee) {
      trackTitle.classList.remove('marquee');
      return;
    }
    const containerWidth = titleScroller.clientWidth;
    const titleWidth = trackTitle.scrollWidth;
    if (titleWidth > containerWidth + 10) {
      trackTitle.style.setProperty('--container-width', `${containerWidth}px`);
      trackTitle.classList.add('marquee');
    } else {
      trackTitle.classList.remove('marquee');
    }
  }

  // Inject user configuration into CSS variables and classes
  function applyConfig(cfg) {
    currentConfig = cfg;

    // Positioning
    stage.className = `obs-stage pos-${cfg.position || 'bottom-left'}`;

    // Card orientation and chassis style
    const chassis = cfg.chassisStyle || 'capsule';
    card.className = `spotify-card style-${chassis} orientation-${cfg.orientation || 'horizontal'}`;
    if (!isPlaying && cfg.dimWhenPaused) {
      card.classList.add('is-paused');
    }

    // Variables on root
    const root = document.documentElement;

    // Dimensions & Offsets
    root.style.setProperty('--scale', (cfg.scale || 100) / 100);
    root.style.setProperty('--offset-x', `${cfg.offsetX || 40}px`);
    root.style.setProperty('--offset-y', `${cfg.offsetY || 40}px`);
    root.style.setProperty('--card-width', `${cfg.cardWidth || 520}px`);
    root.style.setProperty('--card-padding', `${cfg.cardPadding || 14}px`);
    root.style.setProperty('--gap', `${cfg.gap || 16}px`);

    // Background & Card Appearance
    let bgValue = 'rgba(24, 18, 38, 0.92)';
    const opacityDec = (cfg.bgOpacity ?? 92) / 100;

    if (cfg.bgType === 'solid') {
      bgValue = hexToRgba(cfg.bgColor || '#181226', opacityDec);
      root.style.setProperty('--backdrop-blur', '0px');
    } else if (cfg.bgType === 'gradient') {
      const col1 = hexToRgba(cfg.bgGradient1 || '#1a102a', opacityDec);
      const col2 = hexToRgba(cfg.bgGradient2 || '#0c0816', opacityDec);
      bgValue = `linear-gradient(${cfg.bgGradientAngle || 180}deg, ${col1}, ${col2})`;
      root.style.setProperty('--backdrop-blur', `${cfg.backdropBlur || 16}px`);
    } else if (cfg.bgType === 'transparent') {
      bgValue = 'transparent';
      root.style.setProperty('--backdrop-blur', '0px');
    } else {
      bgValue = hexToRgba(cfg.bgColor || '#181226', opacityDec);
      root.style.setProperty('--backdrop-blur', `${cfg.backdropBlur || 20}px`);
    }

    root.style.setProperty('--bg-style', bgValue);
    root.style.setProperty('--card-radius', `${cfg.cardRadius || 28}px`);
    root.style.setProperty('--border-width', `${cfg.borderWidth || 2}px`);
    root.style.setProperty('--border-color', cfg.borderColor || 'rgba(168, 85, 247, 0.75)');
    root.style.setProperty('--card-shadow', cfg.cardShadow || '0 0 25px rgba(168, 85, 247, 0.45)');

    // Accent Stripes
    if (cfg.accentStripes) {
      if (stripesTop) stripesTop.classList.add('visible');
      if (stripesBottom) stripesBottom.classList.add('visible');
    } else {
      if (stripesTop) stripesTop.classList.remove('visible');
      if (stripesBottom) stripesBottom.classList.remove('visible');
    }

    // Album Protrude
    if (cfg.albumProtrude) {
      albumContainer.classList.add('protrude');
    } else {
      albumContainer.classList.remove('protrude');
    }

    // Album Shape and Size
    root.style.setProperty('--album-size', `${cfg.albumSize || 80}px`);
    root.style.setProperty('--album-border-width', `${cfg.albumBorderWidth || 2}px`);
    root.style.setProperty('--album-border-color', cfg.albumBorderColor || 'rgba(192, 132, 252, 0.8)');
    root.style.setProperty('--album-shadow', cfg.albumShadow ? '0 8px 24px rgba(0, 0, 0, 0.45)' : 'none');

    albumWrap.classList.remove('vinyl-mode');
    albumWrap.classList.remove('mecha-mode');

    if (cfg.albumShape === 'circle') {
      root.style.setProperty('--album-radius', '50%');
    } else if (cfg.albumShape === 'square') {
      root.style.setProperty('--album-radius', '0px');
    } else if (cfg.albumShape === 'vinyl') {
      root.style.setProperty('--album-radius', '50%');
      albumWrap.classList.add('vinyl-mode');
    } else {
      root.style.setProperty('--album-radius', `${cfg.albumRadius || 18}px`);
      if (chassis === 'mecha-hud') {
        albumWrap.classList.add('mecha-mode');
      }
    }

    if (cfg.albumSpin) {
      albumWrap.classList.add('spinning');
    } else {
      albumWrap.classList.remove('spinning');
    }

    // Typography - Title
    root.style.setProperty('--title-font', `'${cfg.titleFont || 'Inter'}', sans-serif`);
    root.style.setProperty('--title-size', `${cfg.titleSize || 18}px`);
    root.style.setProperty('--title-weight', cfg.titleWeight || '700');
    root.style.setProperty('--title-style', cfg.titleItalic ? 'italic' : 'normal');
    root.style.setProperty('--title-color', cfg.titleColor || '#ffffff');
    root.style.setProperty('--title-transform', cfg.titleTransform || 'none');
    root.style.setProperty('--title-shadow', cfg.titleShadow ? '0 2px 8px rgba(0,0,0,0.5)' : 'none');

    // Typography - Artist
    root.style.setProperty('--artist-font', `'${cfg.artistFont || 'Inter'}', sans-serif`);
    root.style.setProperty('--artist-size', `${cfg.artistSize || 14}px`);
    root.style.setProperty('--artist-weight', cfg.artistWeight || '500');
    root.style.setProperty('--artist-style', cfg.artistItalic ? 'italic' : 'normal');
    root.style.setProperty('--artist-color', cfg.artistColor || '#c4b5fd');
    root.style.setProperty('--artist-transform', cfg.artistTransform || 'none');

    // Spotify Badge
    if (cfg.showSpotifyIcon) {
      spotifyBadge.classList.add('visible');
      root.style.setProperty('--spotify-icon-color', cfg.spotifyIconColor || '#1db954');
    } else {
      spotifyBadge.classList.remove('visible');
    }

    // Album text
    root.style.setProperty('--album-font-size', `${cfg.albumFontSize || 12}px`);
    root.style.setProperty('--album-font-color', cfg.albumFontColor || '#777777');
    if (!cfg.showAlbum) {
      trackAlbum.classList.add('hidden');
      artistSeparator.classList.add('hidden');
    } else if (currentTrack && currentTrack.album) {
      trackAlbum.classList.remove('hidden');
      artistSeparator.classList.remove('hidden');
    }

    // Progress Bar
    if (cfg.showProgress === false) {
      progressSection.classList.add('hidden');
    } else {
      progressSection.classList.remove('hidden');
    }

    root.style.setProperty('--progress-height', `${cfg.progressHeight || 6}px`);
    root.style.setProperty('--progress-radius', `${cfg.progressRadius || 3}px`);
    root.style.setProperty('--progress-track-color', cfg.progressTrackColor || 'rgba(255, 255, 255, 0.16)');

    let progressFillStyle = cfg.progressFillColor || '#a855f7';
    if (cfg.progressFillGradient && cfg.progressFillColor2) {
      progressFillStyle = `linear-gradient(90deg, ${cfg.progressFillColor}, ${cfg.progressFillColor2})`;
    }
    root.style.setProperty('--progress-fill-color', progressFillStyle);
    root.style.setProperty('--progress-glow', cfg.progressGlow ? `0 0 10px ${cfg.progressFillColor || '#a855f7'}` : 'none');

    // Progress Thumb Handle
    if (cfg.showProgressThumb) {
      progressThumb.classList.add('visible');
      root.style.setProperty('--thumb-color', cfg.thumbColor || '#ffffff');
    } else {
      progressThumb.classList.remove('visible');
    }

    // Timestamps
    if (cfg.showTimestamps === false) {
      timestampRow.classList.add('hidden');
    } else {
      timestampRow.classList.remove('hidden');
    }
    root.style.setProperty('--timestamp-font', `'${cfg.timestampFont || 'Inter'}', sans-serif`);
    root.style.setProperty('--timestamp-size', `${cfg.timestampSize || 11}px`);
    root.style.setProperty('--timestamp-color', cfg.timestampColor || '#e2e8f0');

    // Equalizer (Title Row Soundwave Icon)
    if (cfg.showEqualizer === false) {
      equalizer.classList.add('hidden');
    } else {
      equalizer.classList.remove('hidden');
    }
    root.style.setProperty('--equalizer-color', cfg.equalizerColor || '#a855f7');

    // Audio Rhythm Waveform Visualizer (Image 2)
    if (cfg.showRhythmWave) {
      rhythmVisualizer.classList.add('visible');
      const rColor = cfg.rhythmColor || '#1db954';
      root.style.setProperty('--rhythm-color', rColor);
      root.style.setProperty('--rhythm-height', `${cfg.rhythmHeight || 36}px`);
      root.style.setProperty('--rhythm-glow', cfg.rhythmGlow ? `0 0 10px ${rColor}` : 'none');
    } else {
      rhythmVisualizer.classList.remove('visible');
    }

    // Pause Badge
    if (cfg.showPauseIcon) {
      pausedBadge.classList.add('visible');
    } else {
      pausedBadge.classList.remove('visible');
    }
    root.style.setProperty('--dim-opacity', (cfg.dimOpacity || 70) / 100);

    // Refresh marquee
    checkMarquee();
  }

  // Convert Hex color to rgba string
  function hexToRgba(hex, alpha) {
    if (!hex) return `rgba(24, 18, 38, ${alpha})`;
    if (hex.startsWith('rgba')) return hex;
    let cleanHex = hex.replace('#', '');
    if (cleanHex.length === 3) {
      cleanHex = cleanHex.split('').map(c => c + c).join('');
    }
    const r = parseInt(cleanHex.substring(0, 2), 16) || 0;
    const g = parseInt(cleanHex.substring(2, 4), 16) || 0;
    const b = parseInt(cleanHex.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // WebSocket Connection
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      retryCount = 0;
      console.log('[Spotify Overlay] Connected to real-time server.');
    };

    ws.onmessage = function (event) {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'config_update') {
          applyConfig(msg.data);
        } else if (msg.type === 'track_update') {
          renderTrack(msg.data);
        }
      } catch (e) {
        console.error('[Spotify Overlay] Message parsing error:', e);
      }
    };

    ws.onclose = function () {
      console.warn('[Spotify Overlay] WebSocket disconnected. Reconnecting...');
      retryCount++;
      const timeout = Math.min(1000 * Math.pow(1.5, retryCount), 8000);
      setTimeout(connectWebSocket, timeout);
    };

    ws.onerror = function (err) {
      console.error('[Spotify Overlay] WebSocket error:', err);
    };
  }

  // Window resize handler for marquee recalculation
  window.addEventListener('resize', () => {
    checkMarquee();
  });

  // Initialize
  connectWebSocket();
  animFrameId = requestAnimationFrame(updateProgressLoop);

  // Expose to window for live preview iframe integration
  window.OverlayController = {
    applyConfig: applyConfig,
    renderTrack: renderTrack
  };
})();
