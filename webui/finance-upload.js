/* HADES owner-only CSV preview implementation. Loaded only by a contextual
 * integration surface; it must not install a permanent global chat button. */
(function () {
  'use strict';

  const buttonId = 'hades-finance-csv-contextual-button';
  const modalId = 'hades-finance-csv-modal';
  const maxBytes = 10 * 1024 * 1024;
  const uploadedFiles = window.__hadesUploadedFileIds || (window.__hadesUploadedFileIds = new Map());
  const isNativeRemove = button => /remove\s+file/i.test(button.getAttribute('aria-label') || '');

  // Open WebUI uploads attachments before it submits the chat turn. Keep only
  // the owner-scoped file id/name pair; the bytes are fetched on demand from
  // the same-origin file endpoint for the preview request.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    try {
      const request = args[0];
      const method = String(args[1]?.method || request?.method || 'GET').toUpperCase();
      const url = String(typeof request === 'string' ? request : request?.url || '');
      if (method === 'POST' && /\/api\/v1\/files\/\?/.test(url)) {
        const payload = await response.clone().json();
        if (payload?.id && payload?.filename) {
          uploadedFiles.set(payload.filename, payload.id);
          window.__hadesAttachmentChanged?.(payload.filename);
        }
      }
    } catch (_) { /* Open WebUI owns upload error rendering. */ }
    return response;
  };

  function authHeaders(extra = {}) {
    const token = window.localStorage.getItem('token');
    return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
  }

  function sessionUserId() {
    try {
      const token = window.localStorage.getItem('token');
      return token ? JSON.parse(atob(token.split('.')[1])).id : '';
    } catch (_) { return ''; }
  }

  function el(tag, props, children) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(([key, value]) => {
      if (key === 'textContent') node.textContent = value;
      else if (key === 'className') node.className = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
      else node.setAttribute(key, value);
    });
    (children || []).forEach(child => node.appendChild(child));
    return node;
  }

  function closeModal() {
    document.getElementById(modalId)?.remove();
  }

  function showResult(target, value, error) {
    target.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    target.style.color = error ? '#ff9b9b' : 'var(--hades-cyan, #64e8f2)';
  }

  function openModal(attachedFile) {
    if (document.getElementById(modalId)) return;
    const file = el('input', { type: 'file', accept: '.csv,text/csv' });
    if (attachedFile) {
      // The browser does not allow copying a FileList into another input.
      // Keep the native attachment as the source and avoid asking the user to
      // select the same statement a second time.
      file._hadesAttachedFile = attachedFile;
      file.style.display = 'none';
    }
    const account = el('input', { type: 'text', placeholder: 'Optional account name; HADES resolves internal IDs' });
    const mapping = el('textarea', { rows: '3' });
    mapping.value = '{"date":"Date","payee":"Payee","amount":"Amount"}';
    const result = el('pre', { role: 'status' });
    let inspected = false;
    result.style.cssText = 'white-space:pre-wrap;max-height:35vh;overflow:auto;margin:12px 0;font-size:12px;';
    const renderInspection = payload => {
      if (payload.status === 'FAILED') return showResult(result, payload.error || 'I could not read that statement.', true);
      const range = payload.date_range ? `${payload.date_range.first}–${payload.date_range.last}` : 'not detected';
      const mappingText = Object.entries(payload.suggested_mapping || {}).map(([key, value]) => `${key} ← ${value}`).join(', ');
      showResult(result, `I found ${payload.row_count ?? 'a'} transaction rows in ${payload.filename}.\nDate range: ${range}.\nSuggested columns: ${mappingText || 'I need help matching the columns.'}\n\nThis is a read-only review. If a live Actual Budget ledger is configured, enter an account name and HADES will resolve the internal ID; otherwise nothing is imported.`, false);
      inspected = payload.status === 'INSPECTED';
      submit.textContent = 'Preview import';
    };
    const submit = el('button', { type: 'button', textContent: 'Review statement', onclick: async () => {
      const selected = file._hadesAttachedFile || (file.files && file.files[0]);
      if (!selected) return showResult(result, 'Choose a CSV file first.', true);
      if (selected.size > maxBytes) return showResult(result, 'CSV exceeds the 10 MiB preview limit.', true);
      let mappingValue;
      try { mappingValue = JSON.stringify(JSON.parse(mapping.value || '{}')); }
      catch (_) { return showResult(result, 'Mapping must be valid JSON.', true); }
      submit.disabled = true;
      showResult(result, 'Uploading for preview…', false);
      try {
        const body = new FormData(); body.append('file', selected, selected.name);
        let endpoint = '/api/v1/hades/finance/inspect';
        if (inspected && account.value.trim()) {
          endpoint = '/api/v1/hades/finance/preview';
          body.append('target_account_id', account.value.trim()); body.append('mapping_json', mappingValue);
        }
        const response = await fetch(endpoint, { method: 'POST', headers: authHeaders(), body });
        const payload = await response.json().catch(() => ({ status: 'FAILED', error: 'Invalid server response.' }));
        if (!response.ok) throw new Error(payload.detail || payload.error || `HTTP ${response.status}`);
        if (endpoint.endsWith('/inspect')) renderInspection(payload);
        else showResult(result, payload.status === 'PREVIEW' ? `I found ${payload.transaction_count} transactions.\n${payload.new_count} look new and ${payload.duplicate_count} look like duplicates.\n\nHADES resolved the requested account before import. Review the details below before confirming.\n\n${JSON.stringify(payload.transactions.slice(0, 10), null, 2)}` : payload, payload.status === 'FAILED');
      } catch (error) {
        showResult(result, error.message || 'Finance preview failed.', true);
      } finally { submit.disabled = false; }
    }});
    const dialog = el('div', { id: modalId });
    dialog.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgb(0 0 0 / 68%);display:grid;place-items:center;padding:20px;';
    const panel = el('section', { role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': `${modalId}-title` });
    panel.style.cssText = 'width:min(680px,100%);max-height:90vh;overflow:auto;background:var(--hades-panel,#101923);color:var(--color-gray-100,#eee);border:1px solid var(--hades-border,#426);border-radius:14px;padding:20px;box-shadow:0 0 32px rgb(0 0 0 / 45%);';
    panel.append(
      el('h2', { id: `${modalId}-title`, textContent: 'Finance CSV preview' }),
      el('p', { textContent: 'Owner-only statement review. I will identify the file first, then ask which account it belongs to. Nothing is imported from this screen.' }),
      el('label', { textContent: 'Statement file' }), file,
      el('label', { textContent: 'Actual Budget account name (optional; HADES resolves internal IDs)' }), account,
      el('details', {}, [el('summary', { textContent: 'Advanced column mapping (optional)' }), mapping]),
      el('div', { style: 'display:flex;gap:8px;margin-top:12px;' }, [submit, el('button', { type: 'button', textContent: 'Close', onclick: closeModal })]),
      result
    );
    dialog.appendChild(panel);
    dialog.addEventListener('click', event => { if (event.target === dialog) closeModal(); });
    document.body.appendChild(dialog);
    file.focus();
  }

  async function resolveAttachedFile(filename) {
    const pair = [...uploadedFiles.entries()].find(([name]) => name === filename) || [...uploadedFiles.entries()].at(-1);
    const id = pair?.[1];
    filename = pair?.[0] || filename;
    if (!id) return null;
    const response = await nativeFetch(`/api/v1/files/${encodeURIComponent(id)}/content`);
    if (!response.ok) return null;
    const blob = await response.blob();
    return new File([blob], filename, { type: 'text/csv' });
  }

  function installContextualAction() {
    if (document.getElementById(buttonId)) return;
    const chip = [...document.querySelectorAll('button')].find(button =>
      /\.csv(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    if (!chip) return;
    const filename = [...uploadedFiles.keys()].find(name => (chip.textContent || '').includes(name))
      || [...uploadedFiles.keys()].at(-1)
      || (chip.textContent || '').trim().split(/\s+/)[0];
    const host = chip.parentElement;
    if (!host) return;
    const button = el('button', { id: buttonId, type: 'button', title: 'Review this CSV with HADES finance', textContent: 'Review CSV', onclick: async () => {
      button.disabled = true;
      const file = await resolveAttachedFile(filename);
      button.disabled = false;
      if (file) openModal(file);
      else openModal();
    }});
    button.style.cssText = 'margin:4px 0 0 8px;border:1px solid var(--hades-border,#426);border-radius:8px;padding:5px 9px;background:var(--hades-panel,#101923);color:var(--hades-cyan,#64e8f2);cursor:pointer;';
    host.appendChild(button);
  }

  function cleanupContextualAction() {
    const hasCsvChip = [...document.querySelectorAll('button')].some(button =>
      /\.csv(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    const hasAnyAttachment = [...document.querySelectorAll('button')].some(isNativeRemove);
    const hasImageChip = [...document.querySelectorAll('button')].some(button =>
      /\.(?:png|jpe?g|webp)(?:\s|$)/i.test(button.textContent || '') && !isNativeRemove(button)
    );
    if (!hasAnyAttachment) uploadedFiles.clear();
    if (!hasCsvChip && (hasImageChip || !hasAnyAttachment)) {
      document.getElementById(buttonId)?.remove();
    }
  }

  // This observer is deliberately scoped to an attached CSV. It never creates
  // a fixed/global action and never performs an owner lookup on the login page.
  new MutationObserver(() => {
    cleanupContextualAction();
    installContextualAction();
  }).observe(document.documentElement, { childList: true, subtree: true });
  window.__hadesCleanupFinanceAction = cleanupContextualAction;
  cleanupContextualAction();
  installContextualAction();
})();
