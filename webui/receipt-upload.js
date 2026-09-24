/* HADES owner-only receipt OCR preview affordance. Contextual only: it must
 * never install a permanent global chat button. */
(() => {
  const buttonId = 'hades-receipt-ocr-contextual-button';
  const modalId = 'hades-receipt-ocr-modal';
  const maxBytes = 10 * 1024 * 1024;
  const uploadedFiles = window.__hadesUploadedFileIds || (window.__hadesUploadedFileIds = new Map());
  const isReceiptImage = filename => /\.(?:png|jpe?g|webp)$/i.test(String(filename || ''));
  const isNativeRemove = button => /remove\s+file/i.test(button.getAttribute('aria-label') || '');
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    try {
      const request = args[0];
      const method = String(args[1]?.method || request?.method || 'GET').toUpperCase();
      const url = String(typeof request === 'string' ? request : request?.url || '');
      if (method === 'POST' && /\/api\/v1\/files\/\?/.test(url)) {
        const payload = await response.clone().json();
        if (payload?.id && payload?.filename && isReceiptImage(payload.filename)) {
          uploadedFiles.set(payload.filename, payload.id);
          window.setTimeout(() => installContextualAction(payload.filename), 0);
        }
      }
    } catch (_) {}
    return response;
  };
  const authHeaders = (extra = {}) => {
    const token = window.localStorage.getItem('token');
    return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
  };
  const el = (tag, props = {}) => Object.assign(document.createElement(tag), props);
  const show = (node, text, error = false) => {
    node.textContent = text;
    node.style.color = error ? '#f87171' : '';
  };
  const humanPreviewError = error => {
    const message = String(error?.message || error || '');
    if (/urlopen|name or service not known|connection refused|failed to fetch|timed out|timeout|HTTP 5\d\d/i.test(message)) {
      return 'The receipt reader is unavailable right now. Nothing was added. Try again in a moment.';
    }
    return message || 'The receipt could not be read. Nothing was added.';
  };
  const renderPreview = (node, value) => {
    node.textContent = '';
    const summary = el('pre', { style: 'white-space:pre-wrap;max-height:35vh;overflow:auto' });
    node.appendChild(summary);
    const lines = [];
    if (value.status === 'FAILED') {
      show(summary, `I couldn't read that receipt. ${value.error || value.detail || 'Try a clearer image.'}`, true);
      return;
    }
    lines.push('Receipt review — nothing has been added yet.');
    if (value.merchant) lines.push(`Merchant: ${value.merchant}`);
    if (value.total !== undefined && value.total !== null) lines.push(`Total: ${value.total}`);
    if (value.requires_review) lines.push('Please review the item names and quantities before adding anything to Grocy.');
    if (value.duplicate) lines.push('This receipt appears to have been submitted before; it will not be applied automatically.');
    const items = Array.isArray(value.items) ? value.items : [];
    if (items.length) {
      lines.push('', 'Items:');
      for (const item of items) {
        const name = item.product_name || item.name || item.raw_text || 'Unidentified item';
        const quantity = item.quantity ? ` × ${item.quantity}` : '';
        const state = item.resolution === 'EXACT' ? 'matched' : 'needs review';
        lines.push(`- ${name}${quantity} (${state})`);
      }
    } else if (Array.isArray(value.lines) && value.lines.length) {
      lines.push('', 'Receipt text I found:');
      for (const line of value.lines.slice(0, 32)) {
        if (line && line.text) lines.push(`- ${line.text}`);
      }
      lines.push('', 'I still need a review before these lines can become pantry items.');
    } else {
      lines.push('I could not identify any readable receipt lines.');
    }
    lines.push('', 'Next step: confirm or correct the items in HADES before any Grocy update.');
    show(summary, lines.join('\n'));
    if (!items.length || !value.review_token || !value.receipt_fingerprint) return;

    const controls = el('div', { style: 'display:grid;gap:.75rem;margin-top:1rem' });
    const rows = [];
    for (const item of items) {
      const name = item.name || 'Unidentified item';
      const candidates = Array.isArray(item.candidates) ? item.candidates : [];
      const select = el('select', { ariaLabel: `Choose the pantry item for ${name}` });
      if (item.product_id) {
        select.appendChild(el('option', { value: String(item.product_id), textContent: `${name} — matched` }));
      }
      for (const candidate of candidates) {
        if (!candidate || !candidate.product_id || String(candidate.product_id) === String(item.product_id)) continue;
        select.appendChild(el('option', { value: String(candidate.product_id), textContent: `${candidate.name} — possible match` }));
      }
      if (!select.options.length) {
        select.appendChild(el('option', { value: '', textContent: 'No pantry match found' }));
        select.disabled = true;
      }
      const quantity = el('input', { type: 'number', min: '0.01', step: '0.01', value: '1', ariaLabel: `Quantity of ${name}` });
      const row = el('div', { style: 'display:grid;grid-template-columns:minmax(10rem,1fr) 12rem 7rem;gap:.5rem;align-items:center' });
      row.append(el('label', { textContent: name }), select, quantity);
      controls.appendChild(row);
      rows.push({ name, select, quantity });
    }
    const confirm = el('button', { type: 'button', textContent: 'Confirm and add to pantry' });
    const status = el('div', { style: 'white-space:pre-wrap' });
    confirm.onclick = async () => {
      const applyItems = rows.map(row => ({ name: row.name, product_id: Number(row.select.value), amount: row.quantity.value }));
      if (applyItems.some(item => !item.product_id || !item.amount || Number(item.amount) <= 0)) {
        return show(status, 'Choose a pantry match and positive quantity for every item first.', true);
      }
      confirm.disabled = true;
      show(status, 'Checking the review and updating the shared pantry…');
      try {
        const response = await fetch('/api/v1/hades/receipt/apply', {
          method: 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            confirm: true, receipt_fingerprint: value.receipt_fingerprint,
            review_token: value.review_token, preview_items: items, items: applyItems,
          }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || result.detail || `HTTP ${response.status}`);
        if (result.status === 'SUCCEEDED') {
          show(status, `Added ${applyItems.length} item${applyItems.length === 1 ? '' : 's'} to the shared pantry. Grocy confirmed the update.`);
          confirm.remove();
        } else if (result.status === 'ALREADY APPLIED') {
          show(status, 'This receipt was already added; nothing was duplicated.');
          confirm.remove();
        } else {
          show(status, result.error || 'The pantry update needs reconciliation.', true);
        }
      } catch (error) { show(status, error.message || 'The pantry update failed.', true); }
      finally { confirm.disabled = false; }
    };
    controls.append(el('p', { textContent: 'Review the pantry match and quantity. The shared pantry changes only after you confirm.' }), confirm, status);
    node.appendChild(controls);
  };
  const openModal = (attachedFile) => {
    if (document.getElementById(modalId)) return;
    const result = el('div', { style: 'max-height:55vh;overflow:auto' });
    const input = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp' });
    if (attachedFile) { input._hadesAttachedFile = attachedFile; input.style.display = 'none'; }
    const submit = el('button', { type: 'button', textContent: 'Preview OCR' });
    submit.onclick = async () => {
      const file = input._hadesAttachedFile || input.files?.[0];
      if (!file) return show(result, 'Choose a receipt image first.', true);
      if (file.size > maxBytes) return show(result, 'Image exceeds the 10 MiB preview limit.', true);
      const body = new FormData(); body.append('file', file);
      show(result, 'Running local OCR preview…'); submit.disabled = true;
      try {
        const response = await fetch('/api/v1/hades/receipt/preview', { method: 'POST', headers: authHeaders(), body });
        const value = await response.json();
        if (!response.ok) throw new Error(value.detail || value.error || `HTTP ${response.status}`);
        renderPreview(result, value);
      } catch (error) { show(result, humanPreviewError(error), true); }
      finally { submit.disabled = false; }
    };
    const modal = el('div', { id: modalId, style: 'position:fixed;z-index:9999;inset:10% 10%;padding:2rem;background:var(--color-gray-900,#111827);border:1px solid #555;overflow:auto' });
    const close = el('button', { type: 'button', textContent: 'Close', onclick: () => modal.remove() });
    modal.append(el('h2', { textContent: 'Add items from a receipt' }), el('p', { textContent: 'Upload a clear receipt photo. HADES will read it and show a review. The shared pantry changes only after you confirm. No finance write occurs from this screen.' }), input, submit, close, result);
    document.body.appendChild(modal);
  };
  const resolveAttachedFile = async (filename) => {
    const pair = [...uploadedFiles.entries()].find(([name]) => name === filename) || [...uploadedFiles.entries()].at(-1);
    if (!pair) return null;
    const response = await nativeFetch(`/api/v1/files/${encodeURIComponent(pair[1])}/content`);
    if (!response.ok) return null;
    const lower = pair[0].toLowerCase();
    const type = lower.endsWith('.png') ? 'image/png' : lower.endsWith('.webp') ? 'image/webp' : 'image/jpeg';
    return new File([await response.blob()], pair[0], { type });
  };
  const installContextualAction = (uploadedFilename) => {
    if (uploadedFilename && !isReceiptImage(uploadedFilename)) return;
    if (document.getElementById(buttonId)) return;
    const chip = [...document.querySelectorAll('button')].find(button =>
      /\.(?:png|jpe?g|webp)(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    // Never create a receipt action on an ordinary chat or login shell. A
    // missing visible chip is allowed only after Open WebUI has reported a
    // real uploaded image through the wrapped upload response.
    const imageFiles = [...uploadedFiles.keys()].filter(isReceiptImage);
    if (!chip && !uploadedFilename && !imageFiles.length) return;
    const filename = imageFiles.find(name => (chip?.textContent || '').includes(name))
      || uploadedFilename
      || imageFiles.at(-1)
      || (chip?.textContent || '').trim().split(/\s+/)[0];
    const editable = document.querySelector('textarea, [contenteditable="true"]');
    const host = chip?.parentElement || (imageFiles.length ? editable?.closest('form') || editable?.parentElement?.parentElement : null);
    if (!host) return;
    const button = el('button', { id: buttonId, type: 'button', title: 'Review this receipt with HADES', textContent: 'Review receipt' });
    button.onclick = async () => {
      button.disabled = true;
      const file = await resolveAttachedFile(filename);
      button.disabled = false;
      openModal(file || undefined);
    };
    button.style.cssText = 'margin:4px 0 0 8px;border:1px solid var(--hades-border,#426);border-radius:8px;padding:5px 9px;background:var(--hades-panel,#101923);color:var(--hades-cyan,#64e8f2);cursor:pointer;';
    host.appendChild(button);
  };
  const cleanupContextualAction = () => {
    const hasImageChip = [...document.querySelectorAll('button')].some(button =>
      /\.(?:png|jpe?g|webp)(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    const hasAnyAttachment = [...document.querySelectorAll('button')].some(isNativeRemove);
    const hasCsvChip = [...document.querySelectorAll('button')].some(button =>
      /\.csv(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    if (!hasAnyAttachment) uploadedFiles.clear();
    if (!hasImageChip && (hasCsvChip || !hasAnyAttachment)) {
      document.getElementById(buttonId)?.remove();
    }
  };
  window.__hadesAttachmentChanged = installContextualAction;
  new MutationObserver(() => {
    cleanupContextualAction();
    installContextualAction();
  }).observe(document.documentElement, { childList: true, subtree: true });
  window.__hadesCleanupReceiptAction = cleanupContextualAction;
  cleanupContextualAction();
  installContextualAction();
  // Open WebUI may finish its attachment upload without leaving a visible
  // chip in the composer. Poll only while an uploaded image exists; this does
  // not create a global control on ordinary chats or the login shell.
  window.setInterval(() => {
    const imageFiles = [...uploadedFiles.keys()].filter(isReceiptImage);
    if (imageFiles.length) installContextualAction(imageFiles.at(-1));
  }, 500);
})();
