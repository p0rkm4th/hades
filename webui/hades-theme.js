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

  function saveRemotePreference(key, value) {
    // User settings are the account-level source of truth. localStorage is
    // retained as an offline/failure fallback for older or unauthenticated
    // Open WebUI deployments.
    fetch('/api/v1/users/user/settings/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value })
    }).catch(() => {});
  }

  async function loadRemotePreferences() {
    try {
      const userResponse = await fetch('/api/v1/users/user');
      if (!userResponse.ok) return;
      const user = await userResponse.json();
      const nextScope = String(user.id || '');
      if (!nextScope) return;
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
      const response = await fetch('/api/v1/users/user/settings?raw=true');
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
    restoreTheme(select);
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
  new MutationObserver(() => requestAnimationFrame(install)).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('click', event => {
    if (event.target.closest('#model-selector-model-button, [role="option"][data-value]'))
      requestAnimationFrame(() => requestAnimationFrame(updateToolNotice));
  }, true);
  install();
  loadRemotePreferences();
  // Open WebUI can render the login shell before authentication completes.
  // Retry after the authenticated app has mounted so account preferences
  // apply on a fresh device without requiring a manual reload.
  setTimeout(loadRemotePreferences, 3000);
  setTimeout(loadRemotePreferences, 8000);
})();
