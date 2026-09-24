/* HADES presets/effects layered onto Open WebUI's native settings controls. */
(function () {
  const themeKey = 'hades-odysseus-theme';
  const effectKey = 'hades-background-effect';
  const remoteThemeKey = 'hades_theme';
  const remoteEffectKey = 'hades_background_effect';
  let localThemeChanged = false;
  let localEffectChanged = false;
  let preferenceScope = '';
  const preferenceStorageKey = key => preferenceScope ? `${key}:${preferenceScope}` : key;
  const getLocalPreference = key => localStorage.getItem(preferenceStorageKey(key));
  const setLocalPreference = (key, value) => localStorage.setItem(preferenceStorageKey(key), value);
  const removeLocalPreference = key => localStorage.removeItem(preferenceStorageKey(key));
  const authHeaders = (extra = {}) => {
    const token = localStorage.getItem('token');
    return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
  };
  const sessionUserId = () => {
    try {
      const token = localStorage.getItem('token');
      return token ? JSON.parse(atob(token.split('.')[1])).id : '';
    } catch (_) { return ''; }
  };
  const themes = [
    ['odysseus-neon', '⚡ Odysseus Neon'], ['odysseus-midnight', '🌌 Odysseus Midnight'],
    ['odysseus-cyberpunk', '🟪 Odysseus Cyberpunk'], ['odysseus-retrowave', '🟣 Odysseus Retrowave'],
    ['odysseus-forest', '🌲 Odysseus Forest'], ['odysseus-ocean', '🌊 Odysseus Ocean'],
    ['odysseus-ume', '🌸 Odysseus Ume'], ['odysseus-copper', '🟠 Odysseus Copper'],
    ['odysseus-terminal', '▣ Odysseus Terminal'], ['odysseus-organs', '♥ Odysseus Organs'],
    ['odysseus-lavender', '✿ Odysseus Lavender'], ['odysseus-gpt', '◉ Odysseus GPT'],
    ['odysseus-claude', '◐ Odysseus Claude'], ['odysseus-cute', '♡ Odysseus Cute']
  ];
  const effects = [
    ['none', 'None'], ['dots', '· Dots'], ['synapse', '▦ Synapse Grid'], ['rain', '☔ Rain'],
    ['constellations', '✧ Constellations'], ['perlin-flow', '〰 Perlin Flow'],
    ['petals', '❀ Petals'], ['sparkles', '✦ Sparkles'], ['embers', '✹ Embers']
  ];
  const defaultEffects = {
    'odysseus-neon': 'synapse', 'odysseus-midnight': 'rain',
    'odysseus-cyberpunk': 'synapse', 'odysseus-retrowave': 'embers',
    'odysseus-forest': 'petals', 'odysseus-ocean': 'constellations',
    'odysseus-ume': 'petals', 'odysseus-terminal': 'perlin-flow',
    'odysseus-organs': 'rain', 'odysseus-cute': 'sparkles'
  };
  const themeClasses = themes.map(([value]) => 'hades-theme-' + value);
  const effectClasses = effects.map(([value]) => 'hades-effect-' + value);
  const isTheme = value => themes.some(([candidate]) => candidate === value);
  const isEffect = value => effects.some(([candidate]) => candidate === value);

  function humanizeNativeCapabilityErrors(root = document) {
    const nodes = root.querySelectorAll?.('*') || [];
    for (const node of nodes) {
      if (node.children.length || !node.textContent) continue;
      if (/Permission denied when accessing microphone:\s*NotSupportedError:\s*Not supported/i.test(node.textContent)) {
        node.textContent = 'Voice input is not available in this browser or on this device.';
      }
    }
  }

  function labelVoiceRecordingCancel(root = document) {
    const confirm = root.querySelector?.('#confirm-recording-button');
    if (!confirm) return;
    let bar = confirm.parentElement;
    while (bar && bar !== document.body) {
      const buttons = [...bar.querySelectorAll?.('button') || []];
      if (buttons.length === 2 && buttons.includes(confirm)) {
        const cancel = buttons.find(button => button !== confirm);
        if (cancel && !cancel.getAttribute('aria-label')) {
          cancel.setAttribute('aria-label', 'Cancel recording');
          cancel.title = 'Cancel recording';
        }
        return;
      }
      bar = bar.parentElement;
    }
  }

  function showVoiceFailureNotice() {
    const form = document.querySelector('#message-input-container')?.closest('form') || document.body;
    let notice = document.getElementById('hades-voice-failure-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'hades-voice-failure-notice';
      notice.setAttribute('role', 'alert');
      notice.setAttribute('aria-live', 'assertive');
      notice.style.cssText = 'padding:0 12px 4px;color:var(--color-gray-400,#9ca3af);font-size:.75rem;';
      form.appendChild(notice);
    }
    notice.textContent = 'Voice transcription is unavailable right now. Try recording again or type your message.';
    clearTimeout(showVoiceFailureNotice.timer);
    showVoiceFailureNotice.timer = setTimeout(() => notice.remove(), 7000);
  }

  function showTtsFailureNotice() {
    const form = document.querySelector('#message-input-container')?.closest('form') || document.body;
    let notice = document.getElementById('hades-tts-failure-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'hades-tts-failure-notice';
      notice.setAttribute('role', 'status');
      notice.setAttribute('aria-live', 'polite');
      notice.style.cssText = 'padding:0 12px 4px;color:var(--color-gray-400,#9ca3af);font-size:.75rem;';
      form.appendChild(notice);
    }
    notice.textContent = 'Read Aloud is unavailable right now. The text response is still available.';
    clearTimeout(showTtsFailureNotice.timer);
    showTtsFailureNotice.timer = setTimeout(() => notice.remove(), 7000);
  }

  function saveRemotePreference(key, value) {
    // User settings are the account-level source of truth. localStorage is
    // retained as an offline/failure fallback for older or unauthenticated
    // Open WebUI deployments.
    fetch('/api/v1/users/user/settings/update', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ [key]: value })
    }).catch(() => {});
  }

  async function loadRemotePreferences() {
    try {
      const userId = sessionUserId();
      if (!userId) return;
      // The authenticated token already provides the stable subject used to
      // scope browser-local fallbacks.  The user-by-ID endpoint is an admin
      // surface in current Open WebUI releases and returns 401 for ordinary
      // authenticated users.  Calling it here caused needless console noise
      // and made the theme depend on a privilege the chat UI does not need.
      const nextScope = String(userId);
      if (preferenceScope !== nextScope) {
        preferenceScope = nextScope;
        localThemeChanged = false;
        localEffectChanged = false;
        // Older releases used these unscoped keys. Remove them once the
        // authenticated subject is known so a legacy Neon value cannot flash
        // back into a different account before its remote settings arrive.
        localStorage.removeItem(themeKey);
        localStorage.removeItem(effectKey);
      }
      const response = await fetch('/api/v1/users/user/settings?raw=true', { headers: authHeaders() });
      if (!response.ok) return;
      const settings = await response.json();
      // localStorage is shared by every account using this browser profile,
      // while these settings are account-scoped in Open WebUI. A stale local
      // value must therefore never override an authenticated account value.
      // The synchronous startup restore remains useful while this request is
      // in flight and when the deployment is logged out/offline.
      if (!localThemeChanged && settings && isTheme(settings[remoteThemeKey])) {
        setLocalPreference(themeKey, settings[remoteThemeKey]);
        applyTheme(settings[remoteThemeKey]);
      } else if (!localThemeChanged && settings && !isTheme(settings[remoteThemeKey])) {
        // A native Open WebUI theme is represented by the absence of a HADES
        // preset. Clear an old account/browser preset instead of resurrecting
        // it on the next reload.
        removeLocalPreference(themeKey);
        applyTheme('');
      }
      if (!localEffectChanged && settings && isEffect(settings[remoteEffectKey])) {
        setLocalPreference(effectKey, settings[remoteEffectKey]);
        applyEffect(settings[remoteEffectKey]);
      }
      requestAnimationFrame(install);
    } catch (_) {
      // Keep the local preference when the deployment is offline or logged out.
    }
  }
  let effectCanvas;
  let activeEffect = '';
  let effectFrame;
  function stopEffect() {
    if (effectFrame) cancelAnimationFrame(effectFrame);
    effectFrame = null;
    if (effectCanvas) effectCanvas.remove();
    effectCanvas = null;
    activeEffect = '';
  }
  function startEffect(mode) {
    stopEffect();
    activeEffect = mode;
    if (!mode || mode === 'none' || !document.body) return;
    const canvas = effectCanvas = document.createElement('canvas');
    canvas.id = 'hades-' + mode + '-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    // The chat shell is transparent while an effect is active, so keep the
    // animation behind text and controls instead of tinting the interface.
    canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:1;opacity:.72';
    // Keep the animation inside Open WebUI's app stacking context. A body-level
    // z-index-0 canvas sits behind the app shell and is invisible there.
    (document.querySelector('.app') || document.body).prepend(canvas);
    const ctx = canvas.getContext('2d'); let w = 0; let h = 0; let t = 0;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const color = () => getComputedStyle(document.documentElement).getPropertyValue('--hades-cyan').trim() || '#64e8f2';
    const resize = () => { w = innerWidth; h = innerHeight; canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resize(); addEventListener('resize', resize);
    const count = mode === 'rain' ? 130 : mode === 'perlin-flow' ? 200 : mode === 'embers' ? 70 : mode === 'sparkles' ? 70 : 55;
    const dots = Array.from({ length: count }, () => ({
      x: Math.random() * w, y: Math.random() * h, vx: Math.random() - .5,
      vy: .3 + Math.random() * 1.4, phase: Math.random() * Math.PI * 2,
      size: 1 + Math.random() * 3, life: Math.random(), maxLife: 220 + Math.random() * 220,
      wobble: Math.random() * Math.PI * 2, axis: Math.random() > .5 ? 'x' : 'y', speed: 2 + Math.random() * 8
    }));
    const noise = (x, y) => { const n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453; return n - Math.floor(n); };
    const smoothNoise = (x, y) => { const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
      const a = noise(ix, iy), b = noise(ix + 1, iy), c = noise(ix, iy + 1), d = noise(ix + 1, iy + 1);
      const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
      return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
    };
    const rgb = (hex, alpha) => { const m = hex.match(/^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i); return m ? `rgba(${parseInt(m[1],16)},${parseInt(m[2],16)},${parseInt(m[3],16)},${alpha})` : `rgba(100,232,242,${alpha})`; };
    const resetEmber = p => { p.x = Math.random() * w; p.y = h + Math.random() * 40; p.vx = (Math.random() - .5) * .3; p.vy = -.3 - Math.random() * .8; p.size = .3 + Math.random() * .6; p.life = 0; p.maxLife = 220 + Math.random() * 220; p.wobble = Math.random() * Math.PI * 2; };
    if (mode === 'embers') dots.forEach(p => { resetEmber(p); p.y = Math.random() * h; p.life = Math.random() * p.maxLife; });
    function draw() {
      if (effectCanvas !== canvas || !document.documentElement.classList.contains('hades-effect-' + mode)) { removeEventListener('resize', resize); return; }
      effectFrame = requestAnimationFrame(draw); t += .01;
      if (mode === 'embers' || mode === 'perlin-flow') { ctx.globalCompositeOperation = 'destination-out'; ctx.fillStyle = 'rgba(0,0,0,.12)'; ctx.fillRect(0, 0, w, h); ctx.globalCompositeOperation = 'source-over'; }
      else ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color(); ctx.strokeStyle = color();
      for (const p of dots) {
        if (mode === 'dots') { ctx.globalAlpha = .16; ctx.beginPath(); ctx.arc(p.x, p.y, 1.1, 0, Math.PI * 2); ctx.fill(); }
        else if (mode === 'rain') { p.y += p.vy * 5; if (p.y > h + 30) p.y = -30; const g = ctx.createLinearGradient(p.x, p.y - 28, p.x, p.y); g.addColorStop(0, 'transparent'); g.addColorStop(1, color()); ctx.strokeStyle = g; ctx.globalAlpha = .42; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(p.x, p.y - 24); ctx.lineTo(p.x, p.y); ctx.stroke(); }
        else if (mode === 'petals') { p.y += p.vy; p.x += Math.sin(t + p.phase) * .35; if (p.y > h + 15) p.y = -10; ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(Math.sin(t + p.phase)); ctx.globalAlpha = .2; ctx.beginPath(); ctx.ellipse(-p.size*.2, 0, p.size*.6, p.size*.3, .3, 0, Math.PI*2); ctx.fill(); ctx.globalAlpha = .15; ctx.beginPath(); ctx.ellipse(p.size*.2, 0, p.size*.6, p.size*.3, -.3, 0, Math.PI*2); ctx.fill(); ctx.restore(); }
        else if (mode === 'sparkles') {
          const twinkle = Math.sin(t * 3 + p.phase), a = Math.max(0, twinkle) * .55;
          if (a > .01) { const r = p.size * (.7 + Math.max(0, twinkle) * .9); ctx.save(); ctx.translate(p.x, p.y); ctx.globalAlpha = a; ctx.beginPath(); ctx.moveTo(0, -r); ctx.quadraticCurveTo(r*.15, -r*.15, r, 0); ctx.quadraticCurveTo(r*.15, r*.15, 0, r); ctx.quadraticCurveTo(-r*.15, r*.15, -r, 0); ctx.quadraticCurveTo(-r*.15, -r*.15, 0, -r); ctx.fill(); ctx.restore(); }
        }
        else if (mode === 'embers') {
          p.wobble += .03; p.x += p.vx + Math.sin(p.wobble) * .5; p.y += p.vy; p.life += 1;
          if (p.life > p.maxLife || p.y < -20) resetEmber(p);
          const ratio = p.life / p.maxLife, fade = Math.min(1, Math.min(ratio * 4, (1 - ratio) * 3)), r = p.size * 2.4;
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4); g.addColorStop(0, rgb(color(), .9 * fade)); g.addColorStop(.4, rgb(color(), .28 * fade)); g.addColorStop(1, rgb(color(), 0));
          ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = g; ctx.globalAlpha = 1; ctx.fillRect(p.x-r*4, p.y-r*4, r*8, r*8); ctx.fillStyle = '#fff'; ctx.globalAlpha = .45 * fade; ctx.beginPath(); ctx.arc(p.x, p.y, r*.5, 0, Math.PI*2); ctx.fill(); ctx.globalCompositeOperation = 'source-over';
        }
        else if (mode === 'perlin-flow') {
          const n = smoothNoise(p.x * .004 + t * .08, p.y * .004 + 100), angle = n * Math.PI * 6;
          const speed = 1 + smoothNoise(p.x * .003, p.y * .003 + 50) * 1.5, ox = p.x, oy = p.y;
          p.x += Math.cos(angle) * speed; p.y += Math.sin(angle) * speed; p.life -= .001;
          if (p.life <= 0 || p.x < 0 || p.x > w || p.y < 0 || p.y > h) { p.x = Math.random()*w; p.y = Math.random()*h; p.life = 1; }
          ctx.globalAlpha = p.life * .22; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(p.x, p.y); ctx.stroke();
        }
        else if (mode === 'constellations') { p.x += p.vx; p.y += p.vy; if (p.x < 0) p.x=w; if (p.x>w) p.x=0; if (p.y<0) p.y=h; if (p.y>h) p.y=0; ctx.globalAlpha = .18 + Math.sin(t * 2 + p.phase) * .12; ctx.beginPath(); ctx.arc(p.x, p.y, .8 + p.size*.25, 0, Math.PI * 2); ctx.fill(); }
        else if (mode === 'synapse') { if (p.axis === 'x') p.x += p.speed; else p.y += p.speed; if (p.x > w + 12) p.x = -12; if (p.y > h + 12) p.y = -12; const gx=Math.round(p.x/24)*24, gy=Math.round(p.y/24)*24; ctx.globalAlpha = .45; ctx.beginPath(); ctx.arc(gx, gy, 1.2, 0, Math.PI * 2); ctx.fill(); }
      }
      if (mode === 'constellations') { ctx.globalAlpha = .1; for (let i = 0; i < dots.length; i++) for (let j = i + 1; j < dots.length; j++) { const dx = dots[i].x - dots[j].x, dy = dots[i].y - dots[j].y; if (dx * dx + dy * dy < 110 * 110) { ctx.beginPath(); ctx.moveTo(dots[i].x, dots[i].y); ctx.lineTo(dots[j].x, dots[j].y); ctx.stroke(); } } }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    draw();
  }
  function applyTheme(value) {
    document.documentElement.classList.remove(...themeClasses);
    if (themes.some(([v]) => v === value)) {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark', 'hades-theme-' + value);
    }
  }
  function applyEffect(value) {
    document.documentElement.classList.remove(...effectClasses);
    const selected = value || 'none';
    document.documentElement.classList.add('hades-effect-' + selected);
    if (activeEffect !== selected) { activeEffect = selected; requestAnimationFrame(() => startEffect(selected)); }
  }
  function restoreTheme(select) {
    const saved = getLocalPreference(themeKey);
    if (!themes.some(([v]) => v === saved)) return;
    const option = [...select.options].find(o => o.dataset.hadesTheme === saved);
    if (option && select.value !== saved) select.value = saved;
    if (option) {
      document.documentElement.classList.remove('light');
      document.documentElement.classList.add('dark');
      applyTheme(saved);
    }
  }
  function moveLanguageBeforeTheme(select) {
    const themeRow = select.closest('.flex.items-center.justify-between') || select.parentElement?.parentElement?.parentElement;
    if (!themeRow) return;
    const rows = [...(themeRow.parentElement?.children || [])];
    const languageRow = rows.find(row => /^\s*Language\s*$/i.test(row.querySelector('div.min-w-0')?.textContent || ''));
    if (languageRow && languageRow !== themeRow && themeRow.previousElementSibling !== languageRow)
      themeRow.parentElement.insertBefore(languageRow, themeRow);
  }
  function arrangeSettingDescriptions(select) {
    const themeRow = select.closest('.flex.items-center.justify-between') || select.parentElement?.parentElement?.parentElement;
    const parent = themeRow?.parentElement;
    if (!themeRow || !parent) return;
    const children = [...parent.children];
    const languageRow = children.find(row => row.querySelector('select[aria-label="Language"]'));
    const languageHelp = children.find(row => /^Choose the language used for interface text\.?$/i.test(row.textContent.trim()));
    const translationHelp = children.find(row => /^Couldn't find your language\?/i.test(row.textContent.trim()));
    const colorHelp = children.find(row => /^Choose the color theme used by the interface\.?$/i.test(row.textContent.trim()));
    let anchor = languageRow;
    for (const node of [languageHelp, translationHelp]) {
      if (node && anchor) { anchor.after(node); anchor = node; }
    }
    if (colorHelp) themeRow.after(colorHelp);
  }
  function markComposer() {
    document.querySelectorAll('[contenteditable="true"]').forEach(editable => {
      const surface = editable.closest('.shadow-lg.rounded-3xl') || editable.parentElement?.parentElement?.parentElement;
      if (surface) surface.classList.add('hades-composer-surface');
    });
  }
  function selectedModelName() {
    const button = document.querySelector('#model-selector-model-button[aria-label^="Selected model:"]');
    return button?.getAttribute('aria-label')?.replace(/^Selected model:\s*/, '').trim() || button?.textContent?.trim() || '';
  }
  function updateToolNotice() {
    const name = selectedModelName();
    const dolphin = /dolphin\s+mistral/i.test(name);
    const uncensored = /dolphin(?:[-\s](?:llama3|3))?|heretic|uncensored|abliterated/i.test(name);
    const qwenSmall = /qwen3:8b/i.test(name);
    const noTools = dolphin || uncensored;
    const composer = document.querySelector('[contenteditable="true"]')?.closest('.hades-composer-surface') ||
      document.querySelector('[contenteditable="true"]')?.parentElement?.parentElement?.parentElement;
    if (!composer) return;
    let notice = document.getElementById('hades-model-capability-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'hades-model-capability-notice';
      notice.setAttribute('role', 'status');
      notice.setAttribute('aria-live', 'polite');
      composer.parentElement?.insertBefore(notice, composer);
    }
    if (!name || (!noTools && !qwenSmall)) { notice.hidden = true; notice.textContent = ''; return; }
    notice.hidden = false;
    const modelLabel = noTools ? name : 'Qwen3 8B';
    const capability = noTools ? 'is completion-only and cannot use HADES tools' : 'has limited tool reliability';
    notice.innerHTML = '<span aria-hidden="true">ⓘ</span><span><strong>' + modelLabel + '</strong> is a fast local model that ' + capability + '. Switch to <strong>Hermes Agent</strong> when you need HADES memory, web search, or actions.</span>';
  }
  function install() {
    const select = document.querySelector('select[aria-label="Theme"]');
    applyEffect(getLocalPreference(effectKey) || 'none');
    markComposer();
    labelVoiceRecordingCancel();
    updateToolNotice();
    if (!select) return;
    moveLanguageBeforeTheme(select);
    if (!select.dataset.hadesThemes) {
      select.dataset.hadesThemes = 'true';
      select.querySelectorAll('option[data-hades-theme], option[value^="odysseus-"]').forEach(option => option.remove());
      for (const [value, label] of themes) {
        const option = new Option(label, value);
        option.dataset.hadesTheme = value;
        select.append(option);
      }
      select.addEventListener('change', event => {
        if (event.__hadesThemeHandled) return;
        event.__hadesThemeHandled = true;
        const value = event.target.selectedOptions[0]?.dataset.hadesTheme || '';
        if (value) {
          localThemeChanged = true;
          setLocalPreference(themeKey, value);
          saveRemotePreference(remoteThemeKey, value);
          const applySelectedTheme = () => {
            document.documentElement.classList.remove('light');
            document.documentElement.classList.add('dark');
            applyTheme(value);
            if (!getLocalPreference(effectKey) || getLocalPreference(effectKey) === 'none') {
              const defaultEffect = defaultEffects[value] || 'none';
              setLocalPreference(effectKey, defaultEffect);
              applyEffect(defaultEffect);
              const effectSelect = document.querySelector('select[aria-label="Background effect"]');
              if (effectSelect) effectSelect.value = defaultEffect;
            }
          };
          // Let Open WebUI finish its native select update, then restore the
          // HADES class if its built-in light/dark handler ran afterward.
          requestAnimationFrame(() => {
            applySelectedTheme();
            requestAnimationFrame(applySelectedTheme);
          });
        } else {
          localThemeChanged = true;
          removeLocalPreference(themeKey);
          // Empty is the supported settings value for "no HADES preset";
          // without this write, an older preset (for example Neon) returns
          // after a reload even though the native selector changed.
          saveRemotePreference(remoteThemeKey, '');
          applyTheme('');
        }
      }, true);
    }
    // Once the user has made a native-theme selection, do not let a DOM
    // mutation caused by Open WebUI's own settings update restore the stale
    // HADES preset before the account-level clear finishes saving.
    if (!localThemeChanged) restoreTheme(select);
    const row = select.closest('.flex.items-center.justify-between') || select.parentElement?.parentElement?.parentElement;
    if (row && !row.parentElement.querySelector('select[aria-label="Background effect"]')) {
      const effectRow = row.cloneNode(true);
      effectRow.querySelector('div.min-w-0').textContent = 'Background effect';
      const effectSelect = effectRow.querySelector('select');
      effectSelect.setAttribute('aria-label', 'Background effect');
      effectSelect.title = 'Select a background effect';
      effectSelect.replaceChildren(...effects.map(([value, label]) => new Option(label, value)));
      effectSelect.value = getLocalPreference(effectKey) || 'none';
      effectSelect.addEventListener('change', event => {
        localEffectChanged = true;
        setLocalPreference(effectKey, event.target.value);
        saveRemotePreference(remoteEffectKey, event.target.value);
        applyEffect(event.target.value);
      });
      row.parentElement.insertBefore(effectRow, row.nextSibling);
    }
    arrangeSettingDescriptions(select);
    updateToolNotice();
  }
  const savedThemeAtStartup = getLocalPreference(themeKey);
  if (themes.some(([v]) => v === savedThemeAtStartup)) {
    document.documentElement.classList.remove('light');
    document.documentElement.classList.add('dark');
    applyTheme(savedThemeAtStartup);
  }
  applyEffect(getLocalPreference(effectKey) || 'none');
  new MutationObserver(() => requestAnimationFrame(() => {
    install();
    humanizeNativeCapabilityErrors();
    labelVoiceRecordingCancel();
  })).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('click', event => {
    if (event.target.closest('#model-selector-model-button, [role="option"][data-value]'))
      requestAnimationFrame(() => requestAnimationFrame(updateToolNotice));
  }, true);
  let composerBusyNoticeTimer;
  let composerBusyClearTimer;
  let composerBusyWatchdogTimer;
  let composerBusyHardTimeoutTimer;
  let hadesComposerBusy = false;
  let completionGeneration = 0;
  // /api/chat/completions admits an asynchronous task, and Hades Deep can
  // legitimately spend over 30 seconds in cold-load/prompt work before the
  // first assistant event. Keep this aligned with the bounded Hermes/provider
  // timeout so the browser does not cancel valid Deep work while still
  // recovering a genuinely silent task deterministically.
  const completionSilentTimeoutMs = 180000;
  function clearComposerFailureNotice() {
    document.getElementById('hades-composer-failure-notice')?.remove();
  }
  function renderComposerFailureResult(assistantCountAtStart = 0) {
    const assistants = [...document.querySelectorAll('#response-content-container .markdown-prose')];
    const turnAssistants = assistants.slice(assistantCountAtStart);
    const current = turnAssistants.at(-1);
    const message = 'I could not get a reply from the model. Nothing was changed; please try again.';
    if (current?.getAttribute('data-hades-failure') === 'true') return;
    if (current && !current.innerText?.trim()) {
      current.textContent = message;
      current.setAttribute('data-hades-failure', 'true');
      for (const duplicate of turnAssistants.slice(0, -1)) {
        if (!duplicate.innerText?.trim()) duplicate.remove();
      }
      return;
    }
    const container = document.querySelector('#response-content-container');
    if (!container) return;
    const fallback = document.createElement('div');
    fallback.className = 'markdown-prose';
    fallback.setAttribute('data-hades-failure', 'true');
    fallback.textContent = message;
    container.appendChild(fallback);
  }
  // Open WebUI can replace its Stop control with Send as soon as the user
  // starts typing a follow-up, even while the streaming request is alive.
  // Track the actual completion response instead of trusting that transient
  // button state. The cloned stream is drained separately so the application
  // receives the original response untouched.
  if (!window.__hadesCompletionFetchGuard) {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = function (...args) {
      const request = args[0];
      const url = typeof request === 'string' ? request : request?.url || '';
      const transcription = String(url).includes('/api/v1/audio/transcriptions');
      if (transcription) {
        return nativeFetch(...args).then(response => {
          if (!response.ok) showVoiceFailureNotice();
          return response;
        }, error => {
          showVoiceFailureNotice();
          throw error;
        });
      }
      const speech = /\/v1\/audio\/speech|\/audio\/speech/.test(String(url));
      if (speech) {
        return nativeFetch(...args).then(response => {
          if (!response.ok) showTtsFailureNotice();
          return response;
        }, error => {
          showTtsFailureNotice();
          throw error;
        });
      }
      const completion = String(url).includes('/api/chat/completions');
      if (!completion) return nativeFetch(...args);
      hadesComposerBusy = true;
      clearComposerFailureNotice();
      const generation = ++completionGeneration;
      let failureRendered = false;
      const assistantCountAtStart = document.querySelectorAll('#response-content-container .markdown-prose').length;
      const providerErrorCountAtStart = [...document.querySelectorAll('#response-content-container *')]
        .filter(node => !node.children.length &&
          /there was an issue with the response|connection error|failed to fetch|request timed out|could not get a reply/i.test(node.textContent || '')).length;
      let lastAssistantText = '';
      let assistantStableSince = Date.now();
      const clearWatchdog = () => {
        clearInterval(composerBusyWatchdogTimer);
        composerBusyWatchdogTimer = undefined;
        clearTimeout(composerBusyHardTimeoutTimer);
        composerBusyHardTimeoutTimer = undefined;
      };
      const renderFailureOnce = () => {
        if (failureRendered) return;
        failureRendered = true;
        showComposerFailureNotice(assistantCountAtStart);
      };
      const settleFromRenderedDom = () => {
        if (generation !== completionGeneration) return;
        const assistants = [...document.querySelectorAll('#response-content-container .markdown-prose')];
        const current = assistants.at(-1)?.innerText?.trim() || '';
        if (current !== lastAssistantText) {
          lastAssistantText = current;
          assistantStableSince = Date.now();
        }
        const stopButton = document.querySelector('#message-input-container button[aria-label="Stop"]');
        const renderedNewAssistant = assistants.length > assistantCountAtStart && current;
        const providerErrorCount = [...document.querySelectorAll('#response-content-container *')]
          .filter(node => !node.children.length &&
            /there was an issue with the response|connection error|failed to fetch|request timed out|could not get a reply/i.test(node.textContent || '')).length;
        const renderedProviderError = providerErrorCount > providerErrorCountAtStart ||
          (assistants.length > assistantCountAtStart &&
            /there was an issue with the response|connection error|failed to fetch|request timed out|could not get a reply/i.test(current));
        // Open WebUI renders provider failures as a visible assistant error,
        // but some releases leave the native Stop control active because the
        // websocket error frame does not pass through the normal stream EOF
        // cleanup. Treat the visible error as terminal: release the local
        // guard and click the stale control. This never fires for a healthy
        // stream because it requires a newly rendered error turn.
        if (renderedProviderError) {
          clearWatchdog();
          clearTimeout(composerBusyClearTimer);
          hadesComposerBusy = false;
          completionGeneration += 1;
          if (stopButton) stopButton.click();
          return;
        }
        // The task/websocket path can finish while a stale native Stop control
        // remains rendered. A visibly stable assistant turn is the stronger
        // completion signal here: once the text has stopped changing for a
        // bounded settlement window, release the guard and clear that stale
        // control. Resetting assistantStableSince on every text change keeps
        // this from interrupting a genuinely streaming turn.
        if (renderedNewAssistant && Date.now() - assistantStableSince >= 3000) {
          clearWatchdog();
          clearTimeout(composerBusyClearTimer);
          hadesComposerBusy = false;
          if (stopButton) stopButton.click();
        }
      };
      const expireSilentCompletion = () => {
        if (generation !== completionGeneration || !hadesComposerBusy) return;
        clearWatchdog();
        clearTimeout(composerBusyClearTimer);
        // A provider can return an HTTP 200 stream that never emits a usable
        // assistant turn. Bound that state in the browser as well as in the
        // backend, cancel the current task when the conversation URL gives us
        // its id, and return the composer to a recoverable state.
        const conversationMatch = window.location.pathname.match(/^\/c\/([^/]+)/);
        if (conversationMatch) {
          nativeFetch(`/api/tasks/chat/${encodeURIComponent(conversationMatch[1])}/stop`, {
            method: 'POST', credentials: 'same-origin',
          }).catch(() => {});
        }
        hadesComposerBusy = false;
        completionGeneration += 1;
        renderFailureOnce();
      };
      clearWatchdog();
      composerBusyWatchdogTimer = setInterval(() => {
        if (generation !== completionGeneration) return clearWatchdog();
        settleFromRenderedDom();
        if (generation !== completionGeneration || !hadesComposerBusy) return clearWatchdog();
        if (Date.now() - assistantStableSince < completionSilentTimeoutMs) return;
        expireSilentCompletion();
      }, 250);
      // Keep a separate one-shot timer. Some browsers throttle or suspend
      // interval callbacks while a streaming page is quiet; the hard timer
      // guarantees that a silent provider cannot leave the composer guarded
      // forever merely because the response promise never settles.
      composerBusyHardTimeoutTimer = setTimeout(expireSilentCompletion, completionSilentTimeoutMs);
      return nativeFetch(...args).then(response => {
        const clear = () => {
          clearWatchdog();
          clearTimeout(composerBusyClearTimer);
          // Open WebUI can still be committing the assistant turn after the
          // response body closes. Keep the composer protected for a bounded
          // settlement window so a rapid follow-up cannot create a blank
          // assistant slot during that lifecycle gap.
          composerBusyClearTimer = setTimeout(() => {
            if (generation !== completionGeneration) return;
            const assistants = [...document.querySelectorAll('#response-content-container .markdown-prose')];
            const current = assistants.at(-1)?.innerText?.trim() || '';
            if (assistants.length <= assistantCountAtStart || !current) {
              hadesComposerBusy = false;
              completionGeneration += 1;
              renderFailureOnce();
              const failedStopButton = document.querySelector('#message-input-container button[aria-label="Stop"]');
              if (failedStopButton) failedStopButton.click();
              return;
            }
            hadesComposerBusy = false;
            // Some provider failures close the response without clearing
            // Open WebUI's native Stop control. Wait long enough for Svelte
            // to commit fast completion-only assistant text, then settle the
            // stale control. The response clone is at EOF here, so clicking
            // Stop now cannot truncate an active generation.
            const stopButton = document.querySelector('#message-input-container button[aria-label="Stop"]');
            if (stopButton) stopButton.click();
          }, 5000);
        };
        // Current Open WebUI returns a small JSON task-admission response
        // here. The assistant stream is delivered asynchronously through the
        // task/websocket lifecycle, so EOF on this response is not model
        // completion. Treating JSON admission as stream completion caused the
        // guard to click Stop five seconds later before the real assistant
        // turn arrived. Only an actual SSE response owns EOF cleanup.
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.toLowerCase().includes('text/event-stream')) {
          if (!response.ok) clear();
          return response;
        }
        if (!response.body) { clear(); return response; }
        try {
          const mirror = response.clone();
          (async () => {
            try {
              const reader = mirror.body?.getReader();
              if (reader) while (!(await reader.read()).done) {}
            } catch (_) {
              // The original request owns user-visible failure handling.
            } finally {
              clear();
            }
          })();
        } catch (_) {
          clear();
        }
        return response;
      }, error => {
        clearWatchdog();
        clearTimeout(composerBusyClearTimer);
        hadesComposerBusy = false;
        completionGeneration += 1;
        throw error;
      });
    };
    window.__hadesCompletionFetchGuard = true;
  }
  function showComposerBusyNotice() {
    const form = document.querySelector('#message-input-container')?.closest('form');
    if (!form) return;
    let notice = document.getElementById('hades-composer-busy-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'hades-composer-busy-notice';
      notice.setAttribute('role', 'status');
      notice.setAttribute('aria-live', 'polite');
      notice.style.cssText = 'padding:0 12px 4px;color:var(--color-gray-400,#9ca3af);font-size:.75rem;';
      form.appendChild(notice);
    }
    notice.textContent = "I'm still finishing the last reply. Your message is still in the composer.";
    clearTimeout(composerBusyNoticeTimer);
    composerBusyNoticeTimer = setTimeout(() => { notice.textContent = ''; }, 3500);
  }
  function showComposerFailureNotice(assistantCountAtStart = 0) {
    const form = document.querySelector('#message-input-container')?.closest('form');
    if (!form) return;
    renderComposerFailureResult(assistantCountAtStart);
    document.getElementById('hades-composer-busy-notice')?.remove();
    let notice = document.getElementById('hades-composer-failure-notice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'hades-composer-failure-notice';
      notice.setAttribute('role', 'status');
      notice.setAttribute('aria-live', 'assertive');
      notice.style.cssText = 'padding:0 12px 4px;color:var(--color-gray-400,#9ca3af);font-size:.75rem;';
      form.appendChild(notice);
    }
    notice.textContent = 'I could not get a reply from the model. Nothing was changed; please try again.';
  }
  // Open WebUI optimistically renders a new user turn even when a stream is
  // already active. The active Stop control is the authoritative UI signal;
  // hold accidental Enter/submit events locally instead of creating blank
  // assistant bubbles that can never receive a corresponding response.
  function guardBusyComposerEvent(event) {
    const stopButton = document.querySelector('#message-input-container button[aria-label="Stop"]');
    const busy = hadesComposerBusy || stopButton;
    if (event.type === 'keydown') {
      if (event.key !== 'Enter' || event.shiftKey || !event.target.closest?.('#chat-input')) return;
    } else if (!event.target.closest?.('#message-input-container')) return;
    if (!busy) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showComposerBusyNotice();
  }
  // Capture at window before Open WebUI's document-level handlers. The app
  // can otherwise consume the event first and leave the user with a silent
  // no-op when its transient Stop control and stream state disagree.
  window.addEventListener('keydown', guardBusyComposerEvent, true);
  window.addEventListener('submit', guardBusyComposerEvent, true);
  /* Keep the handler close to the composer contract for browsers/extensions
     that dispatch through document rather than window. The window handler
     normally stops propagation first, so this is only a defensive fallback. */
  document.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.shiftKey || !event.target.closest?.('#chat-input')) return;
    if (!hadesComposerBusy && !document.querySelector('#message-input-container button[aria-label="Stop"]')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showComposerBusyNotice();
  }, true);
  document.addEventListener('submit', event => {
    if (!event.target.closest?.('#message-input-container')) return;
    if (!hadesComposerBusy && !document.querySelector('#message-input-container button[aria-label="Stop"]')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showComposerBusyNotice();
  }, true);
  install();
  // The settings view can replace the native select after the extension has
  // installed its direct listener. Delegation keeps built-in theme changes
  // reliable across those rerenders and account switches.
  document.addEventListener('change', event => {
    const select = event.target.closest?.('select[aria-label="Theme"]');
    if (!select || event.__hadesThemeHandled) return;
    const value = select.selectedOptions[0]?.dataset.hadesTheme || '';
    if (value) return;
    event.__hadesThemeHandled = true;
    localThemeChanged = true;
    removeLocalPreference(themeKey);
    saveRemotePreference(remoteThemeKey, '');
    applyTheme('');
  }, true);
  loadRemotePreferences();
  // Open WebUI can render the login shell before authentication completes.
  // Retry after the authenticated app has mounted so account preferences
  // apply on a fresh device without requiring a manual reload.
  setTimeout(loadRemotePreferences, 3000);
  setTimeout(loadRemotePreferences, 8000);
})();
