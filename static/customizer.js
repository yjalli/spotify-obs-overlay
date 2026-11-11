/* ==========================================================
   Spotify OBS Overlay - Customizer & Dashboard Script
   Handles instant live preview, preset switching, form synchronization,
   and OBS URL copy helper.
   ========================================================== */

(function () {
  'use strict';

  let config = {};
  let ws = null;
  let testModeActive = false;

  // DOM Elements
  const headerTrackInfo = document.getElementById('header-track-info');
  const liveStatusPill = document.getElementById('live-status-pill');
  const btnToggleTest = document.getElementById('btn-toggle-test');
  const btnToggleTestText = document.getElementById('btn-toggle-test-text');
  const btnNextTest = document.getElementById('btn-next-test');
  const btnCopyUrl = document.getElementById('btn-copy-url');
  const btnCopyText = document.getElementById('btn-copy-text');
  const btnCopyCode = document.getElementById('btn-copy-code');
  const obsSourceUrl = document.getElementById('obs-source-url');
  const btnSave = document.getElementById('btn-save');
  const btnReset = document.getElementById('btn-reset');
  const previewStage = document.getElementById('preview-stage');
  const previewFrame = document.getElementById('preview-frame');
  const toast = document.getElementById('toast');

  // Set OBS URL based on current host
  const overlayUrl = `${window.location.origin}/overlay`;
  if (obsSourceUrl) {
    obsSourceUrl.textContent = overlayUrl;
  }

  // Toast Notification
  function showToast(message, duration = 2500) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }

  // Copy to clipboard helper
  function copyToClipboard(text, btnElement, successText = 'Copied!') {
    navigator.clipboard.writeText(text).then(() => {
      const originalText = btnElement.innerHTML;
      btnElement.innerHTML = `✓ ${successText}`;
      btnElement.style.background = '#10b981';
      btnElement.style.color = '#000';
      showToast(`Copied to clipboard: ${text}`);
      setTimeout(() => {
        btnElement.innerHTML = originalText;
        btnElement.style.background = '';
        btnElement.style.color = '';
      }, 2000);
    }).catch(err => {
      console.error('Clipboard copy failed:', err);
      prompt('Copy this URL:', text);
    });
  }

  if (btnCopyUrl) {
    btnCopyUrl.addEventListener('click', () => {
      copyToClipboard(overlayUrl, btnCopyText);
    });
  }

  if (btnCopyCode) {
    btnCopyCode.addEventListener('click', () => {
      copyToClipboard(overlayUrl, btnCopyCode);
    });
  }

  // Background Preview Switcher
  document.querySelectorAll('.bg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.bg-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const bg = btn.dataset.bg;
      previewStage.className = `preview-stage stage-${bg}`;
    });
  });

  // Settings Tabs Switcher
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.dataset.tab;
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Populate UI controls from config object
  function populateUI(cfg) {
    config = Object.assign({}, cfg);

    // Iterate over all bound elements
    document.querySelectorAll('[data-bind]').forEach(el => {
      const key = el.dataset.bind;
      const val = config[key];
      if (val === undefined) return;

      if (el.tagName === 'INPUT') {
        if (el.type === 'checkbox') {
          el.checked = Boolean(val);
        } else if (el.type === 'range') {
          el.value = val;
          const displayEl = document.getElementById(`val-${key}`);
          if (displayEl) {
            let unit = 'px';
            if (key === 'scale' || key === 'bgOpacity' || key === 'dimOpacity') unit = '%';
            if (key === 'bgGradientAngle') unit = '°';
            if (key === 'autoHideDelay') unit = 's';
            displayEl.textContent = `${val}${unit}`;
          }
        } else if (el.type === 'color') {
          if (val.startsWith('#')) {
            el.value = val;
          }
          const labelEl = document.getElementById(`label-${key}`);
          if (labelEl) labelEl.textContent = val;
        }
      } else if (el.tagName === 'SELECT') {
        el.value = val;
      }
    });

    // Update Segmented Controls
    document.querySelectorAll('.segmented-control').forEach(seg => {
      const firstBtn = seg.querySelector('.segment-btn');
      if (!firstBtn) return;
      const key = firstBtn.dataset.bind;
      const currentVal = config[key];
      seg.querySelectorAll('.segment-btn').forEach(btn => {
        if (btn.dataset.val === String(currentVal)) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    });

    // Toggle gradient options visibility
    const gradOptions = document.getElementById('gradient-options');
    if (gradOptions) {
      gradOptions.style.display = (config.bgType === 'gradient') ? 'grid' : 'none';
    }

    // Toggle progress gradient visibility
    const progGrad = document.getElementById('progress-gradient-col');
    if (progGrad) {
      progGrad.style.display = config.progressFillGradient ? 'grid' : 'none';
    }

    // Update Test Mode UI
    testModeActive = Boolean(config.testMode);
    if (btnToggleTest) {
      if (testModeActive) {
        btnToggleTest.classList.remove('btn-secondary');
        btnToggleTest.classList.add('btn-primary');
        btnToggleTestText.textContent = 'Exit Test Mode';
        btnNextTest.style.display = 'inline-flex';
      } else {
        btnToggleTest.classList.remove('btn-primary');
        btnToggleTest.classList.add('btn-secondary');
        btnToggleTestText.textContent = 'Test Song Mode';
        btnNextTest.style.display = 'none';
      }
    }
  }

  // Send live preview update over WebSocket
  function emitLiveConfig(updatedKey, updatedVal) {
    config[updatedKey] = updatedVal;

    // Direct iframe preview update if available
    try {
      if (previewFrame.contentWindow && previewFrame.contentWindow.OverlayController) {
        previewFrame.contentWindow.OverlayController.applyConfig(config);
      }
    } catch (e) {
      // Cross-origin fallback
    }

    // Broadcast through WebSocket to real OBS instances
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'live_preview_config',
        data: config
      }));
    }
  }

  // Bind input listeners
  function setupInputBindings() {
    // Inputs (range, checkbox, select, color)
    document.querySelectorAll('[data-bind]').forEach(el => {
      const key = el.dataset.bind;

      if (el.tagName === 'INPUT') {
        if (el.type === 'range') {
          el.addEventListener('input', () => {
            const val = Number(el.value);
            const displayEl = document.getElementById(`val-${key}`);
            if (displayEl) {
              let unit = 'px';
              if (key === 'scale' || key === 'bgOpacity' || key === 'dimOpacity') unit = '%';
              if (key === 'bgGradientAngle') unit = '°';
              if (key === 'autoHideDelay') unit = 's';
              displayEl.textContent = `${val}${unit}`;
            }
            emitLiveConfig(key, val);
          });
        } else if (el.type === 'checkbox') {
          el.addEventListener('change', () => {
            const val = el.checked;
            if (key === 'progressFillGradient') {
              const progGrad = document.getElementById('progress-gradient-col');
              if (progGrad) progGrad.style.display = val ? 'grid' : 'none';
            }
            emitLiveConfig(key, val);
          });
        } else if (el.type === 'color') {
          el.addEventListener('input', () => {
            const val = el.value;
            const labelEl = document.getElementById(`label-${key}`);
            if (labelEl) labelEl.textContent = val;
            emitLiveConfig(key, val);
          });
        }
      } else if (el.tagName === 'SELECT') {
        el.addEventListener('change', () => {
          emitLiveConfig(key, el.value);
        });
      }
    });

    // Segmented Buttons
    document.querySelectorAll('.segment-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const parent = btn.parentElement;
        parent.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const key = btn.dataset.bind;
        const val = btn.dataset.val;

        if (key === 'bgType') {
          const gradOptions = document.getElementById('gradient-options');
          if (gradOptions) {
            gradOptions.style.display = (val === 'gradient') ? 'grid' : 'none';
          }
        }

        emitLiveConfig(key, val);
      });
    });

    // Border Color picker helper
    const borderColorPicker = document.getElementById('borderColorPicker');
    if (borderColorPicker) {
      borderColorPicker.addEventListener('input', () => {
        const hex = borderColorPicker.value;
        document.getElementById('label-borderColor').textContent = hex;
        emitLiveConfig('borderColor', hex);
      });
    }

    // Progress Track Color picker helper
    const progressTrackColorPicker = document.getElementById('progressTrackColorPicker');
    if (progressTrackColorPicker) {
      progressTrackColorPicker.addEventListener('input', () => {
        const hex = progressTrackColorPicker.value;
        document.getElementById('label-progressTrackColor').textContent = hex;
        emitLiveConfig('progressTrackColor', hex);
      });
    }
  }

  // Presets Click Handler
  document.querySelectorAll('.preset-card').forEach(card => {
    card.addEventListener('click', async () => {
      const presetKey = card.dataset.preset;
      try {
        const res = await fetch(`/api/presets/${presetKey}`, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          populateUI(data.config);
          showToast(`Applied preset: ${card.querySelector('.preset-title').textContent}`);
        }
      } catch (err) {
        console.error('Failed to apply preset:', err);
      }
    });
  });

  // Save Settings to server
  btnSave.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        showToast('Settings saved to config.json!');
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
      showToast('Error saving settings', 3000);
    }
  });

  // Reset to default settings
  btnReset.addEventListener('click', async () => {
    if (!confirm('Reset all overlay customization settings to factory default?')) return;
    try {
      const res = await fetch('/api/reset-config', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        populateUI(data.config);
        showToast('Reset to default settings!');
      }
    } catch (err) {
      console.error('Failed to reset config:', err);
    }
  });

  // Test Mode Toggle
  btnToggleTest.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/test-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !testModeActive })
      });
      if (res.ok) {
        const data = await res.json();
        testModeActive = data.testMode;
        config.testMode = testModeActive;
        populateUI(config);
        showToast(testModeActive ? 'Test mode activated' : 'Exited test mode (live Spotify tracking active)');
      }
    } catch (err) {
      console.error('Failed to toggle test mode:', err);
    }
  });

  // Next Test Song
  btnNextTest.addEventListener('click', async () => {
    try {
      await fetch('/api/test-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true, nextTrack: true })
      });
    } catch (err) {
      console.error('Failed to cycle test song:', err);
    }
  });

  // WebSocket Connection
  function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onmessage = function (event) {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'config_update') {
          populateUI(msg.data);
        } else if (msg.type === 'track_update') {
          updateTrackHeader(msg.data);
        }
      } catch (err) {
        console.error('WebSocket parse error in customizer:', err);
      }
    };

    ws.onclose = function () {
      setTimeout(initWebSocket, 2000);
    };
  }

  // Update Status Pill in Header
  function updateTrackHeader(track) {
    if (track.testMode || config.testMode) {
      liveStatusPill.className = 'status-pill status-active';
      headerTrackInfo.textContent = `⚡ Test Mode: ${track.title} - ${track.artist}`;
      return;
    }

    if (!track.has_track || !track.title || track.title === 'Waiting for Spotify...') {
      liveStatusPill.className = 'status-pill status-waiting';
      headerTrackInfo.textContent = 'Waiting for Spotify playback...';
      return;
    }

    const isPlaying = (track.status === 'PLAYING');
    liveStatusPill.className = `status-pill ${isPlaying ? 'status-active' : 'status-waiting'}`;
    headerTrackInfo.textContent = `${isPlaying ? '▶' : '⏸'} ${track.title} • ${track.artist}`;
  }

  // Initial Data Load
  async function init() {
    setupInputBindings();
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        populateUI(data);
      }
    } catch (e) {
      console.warn('Initial fetch failed, relying on WebSocket');
    }
    initWebSocket();
  }

  init();
})();
