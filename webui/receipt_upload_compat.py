"""Install the HADES owner-scoped receipt review/apply endpoints."""

from pathlib import Path


MAIN = Path("/app/backend/open_webui/main.py")
MARKER = "\n\n##################################\n#\n# Chat Endpoints"
ROUTE = r'''

# HADES receipt OCR upload/apply: same-origin, owner-scoped, review-gated.
@app.post('/api/v1/hades/receipt/preview')
async def hades_receipt_preview(request: Request, user=Depends(get_verified_user)):
    """OCR one inline image without retaining it or changing Grocy/finance."""
    import asyncio as _hades_asyncio
    import base64 as _hades_base64
    import hashlib as _hades_hashlib
    import hmac as _hades_hmac
    import json as _hades_json
    import os as _hades_os
    import tempfile as _hades_tempfile
    import urllib.request as _hades_request

    owner_id = _hades_os.environ.get('HADES_RECEIPT_OWNER_USER_ID', '').strip()
    acceptance_ids = {value.strip() for value in _hades_os.environ.get('HADES_ACCEPTANCE_OWNER_USER_IDS', '').split(',') if value.strip()}
    owner_allowed = (str(getattr(user, 'id', '')) == owner_id and getattr(user, 'role', '') == 'admin') or str(getattr(user, 'id', '')) in acceptance_ids
    if not owner_allowed:
        raise HTTPException(status_code=403, detail='Receipt OCR preview is owner-only.')

    form = await request.form(max_part_size=10 * 1024 * 1024)
    upload = form.get('file')
    if upload is None or not hasattr(upload, 'read'):
        raise HTTPException(status_code=400, detail='An image file is required.')
    filename = str(getattr(upload, 'filename', '') or '')
    mime = str(getattr(upload, 'content_type', '') or '').lower()
    allowed = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}
    suffix = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if mime not in allowed or suffix not in {allowed[mime].lstrip('.'), 'jpeg' if mime == 'image/jpeg' else suffix}:
        raise HTTPException(status_code=400, detail='Only PNG, JPEG, and WebP receipt images are accepted.')
    data = await upload.read()
    if not isinstance(data, bytes) or not data:
        raise HTTPException(status_code=400, detail='The receipt image is empty.')
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='The receipt image exceeds the 10 MiB preview limit.')

    payload = _hades_json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
                   'clientInfo': {'name': 'hades-open-webui-receipt-preview', 'version': '1'}},
    }).encode()
    endpoint = _hades_os.environ.get('HADES_RECEIPT_OCR_URL', 'http://hades-receipt-ocr:8000/mcp')

    def _grocy_key():
        path = _hades_os.environ.get('HADES_RECEIPT_GROCY_API_KEY_FILE', '').strip()
        if not path:
            return ''
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                value = handle.read().strip()
            if not value or len(value) > 4096:
                return ''
            return value
        except OSError:
            return ''

    def _grocy_json(method, path, body=None):
        key = _grocy_key()
        if not key:
            raise RuntimeError('Pantry review is unavailable because its protected service credential is not configured.')
        base = _hades_os.environ.get('HADES_RECEIPT_GROCY_URL', 'http://hades-grocy').rstrip('/')
        encoded = None if body is None else _hades_json.dumps(body).encode()
        headers = {'Accept': 'application/json', 'GROCY-API-KEY': key}
        if encoded is not None:
            headers['Content-Type'] = 'application/json'
        req = _hades_request.Request(f'{base}/api{path}', data=encoded, headers=headers, method=method)
        with _hades_request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8', 'replace')
            return _hades_json.loads(raw) if raw else {}

    def _review_secret():
        value = _hades_os.environ.get('WEBUI_SECRET_KEY', '')
        if not value:
            try:
                value = open('/app/backend/.webui_secret_key', encoding='utf-8').read().strip()
            except OSError:
                value = ''
        if not value:
            raise RuntimeError('Receipt review signing is unavailable.')
        return value.encode()

    def _review_token(fingerprint, items):
        payload = _hades_json.dumps({'fingerprint': fingerprint, 'items': items}, sort_keys=True, separators=(',', ':')).encode()
        return _hades_hmac.new(_review_secret(), payload, _hades_hashlib.sha256).hexdigest()

    def _fingerprint_status(fingerprint, mark=None):
        path = _hades_os.environ.get('HADES_RECEIPT_LEDGER_PATH', '/var/lib/hades-receipt/fingerprints.json')
        parent = _hades_os.path.dirname(path)
        if parent:
            _hades_os.makedirs(parent, mode=0o700, exist_ok=True)
        entries = {}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                value = _hades_json.load(handle)
            if isinstance(value, dict) and isinstance(value.get('fingerprints'), dict):
                entries = value['fingerprints']
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            raise RuntimeError('Receipt duplicate ledger is unavailable or malformed.')
        current = entries.get(fingerprint, {})
        status = current.get('status') if isinstance(current, dict) else None
        if mark is None:
            return status or 'NEW'
        entries[fingerprint] = {'status': mark}
        fd, temporary = _hades_tempfile.mkstemp(prefix='.receipt-ledger.', dir=parent or '.')
        try:
            _hades_os.fchmod(fd, 0o600)
            with _hades_os.fdopen(fd, 'w', encoding='utf-8') as handle:
                _hades_json.dump({'fingerprints': entries}, handle, sort_keys=True)
                handle.write('\\n')
                handle.flush()
                os.fsync(handle.fileno())
            _hades_os.replace(temporary, path)
        finally:
            if _hades_os.path.exists(temporary):
                _hades_os.unlink(temporary)
        return mark

    def _post(body, session_id=None):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        if session_id:
            headers['mcp-session-id'] = session_id
        req = _hades_request.Request(endpoint, data=body, headers=headers, method='POST')
        with _hades_request.urlopen(req, timeout=90) as response:
            return dict(response.headers), response.read().decode('utf-8', 'replace')

    def _message(body):
        for line in body.splitlines():
            if line.startswith('data: '):
                try:
                    value = _hades_json.loads(line[6:])
                except ValueError:
                    continue
                if isinstance(value, dict):
                    return value
        return {}

    def _ocr():
        headers, _ = _post(payload)
        session_id = headers.get('mcp-session-id')
        if not session_id:
            raise RuntimeError('OCR gateway did not return an MCP session.')
        initialized = _hades_json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}).encode()
        _post(initialized, session_id)
        call = _hades_json.dumps({
            'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
            'params': {'name': 'receipt_ocr_extract', 'arguments': {
                'image_base64': _hades_base64.b64encode(data).decode('ascii'), 'mime': mime,
            }},
        }).encode()
        _, body = _post(call, session_id)
        message = _message(body)
        result = message.get('result') or {}
        content = result.get('content') if isinstance(result, dict) else None
        decoded = []
        for item in content or []:
            text = item.get('text') if isinstance(item, dict) else None
            if not isinstance(text, str):
                continue
            try:
                decoded.append(_hades_json.loads(text))
            except ValueError:
                decoded.append({'text': text})
        lines = []

        def _collect(value):
            if isinstance(value, dict):
                texts = value.get('rec_texts')
                scores = value.get('rec_scores')
                if isinstance(texts, list):
                    for index, text in enumerate(texts):
                        if isinstance(text, str) and text.strip():
                            confidence = scores[index] if isinstance(scores, list) and index < len(scores) else None
                            lines.append({'text': ' '.join(text.split()), 'confidence': confidence})
                elif isinstance(value.get('text'), str) and value['text'].strip() and not isinstance(value.get('text_lines'), list):
                    lines.append({'text': ' '.join(value['text'].split()), 'confidence': value.get('confidence')})
                for key in ('content', 'data', 'result', 'ocr', 'text_lines'):
                    _collect(value.get(key))
            elif isinstance(value, str) and value.strip():
                try:
                    _collect(_hades_json.loads(value))
                except ValueError:
                    lines.append({'text': ' '.join(value.split()), 'confidence': None})
            elif isinstance(value, list):
                for item in value:
                    _collect(item)

        _collect(decoded)
        unique_lines = []
        seen = set()
        for line in lines:
            marker = (line.get('text'), line.get('confidence'))
            if marker not in seen:
                seen.add(marker)
                unique_lines.append(line)
        visible_lines = unique_lines[:256]
        import re as _hades_re
        import difflib as _hades_difflib
        amount_re = _hades_re.compile(r'^\$?\d+(?:\.\d{2})?$')
        inline_amount_re = _hades_re.compile(r'^(?P<name>.+?)\s+\$?(?P<amount>\d+(?:\.\d{2})?)$')
        inline_total_re = _hades_re.compile(r'^(?P<name>subtotal|tax|total|amount due)\s*\$?(?P<amount>\d+(?:\.\d{2})?)$', _hades_re.IGNORECASE)
        labels = {'subtotal', 'tax', 'total', 'amount due'}
        merchant = visible_lines[0]['text'] if visible_lines else None
        date = next((line['text'] for line in visible_lines if _hades_re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', line['text'])), None)
        items = []
        totals = {}
        index = 0
        while index < len(visible_lines):
            name = visible_lines[index]['text'].strip()
            amount = None
            step = 1
            inline_total = inline_total_re.fullmatch(name)
            inline_amount = inline_amount_re.fullmatch(name)
            if inline_total:
                name = inline_total.group('name').strip()
                amount = inline_total.group('amount')
            elif inline_amount:
                name = inline_amount.group('name').strip()
                amount = inline_amount.group('amount')
            elif index + 1 < len(visible_lines):
                paired_amount = visible_lines[index + 1]['text'].strip().replace(',', '')
                if amount_re.fullmatch(paired_amount):
                    amount = paired_amount
                    step = 2
            if amount is not None:
                numeric = f'{float(amount.replace("$", "")):.2f}'
                if name.lower() in labels:
                    totals[name.lower()] = numeric
                elif name != merchant and name != date:
                    items.append({'name': name, 'line_total': numeric, 'resolution': 'REVIEW_REQUIRED'})
            index += step
        try:
            products = _grocy_json('GET', '/objects/products')
        except Exception:
            products = []
        normalized_products = []
        for product in products if isinstance(products, list) else []:
            if isinstance(product, dict) and product.get('id') and product.get('name'):
                normalized_products.append({'product_id': int(product['id']), 'name': str(product['name'])})
        for item in items:
            needle = _hades_re.sub(r'[^a-z0-9]+', ' ', item['name'].lower()).strip()
            exact = [p for p in normalized_products if _hades_re.sub(r'[^a-z0-9]+', ' ', p['name'].lower()).strip() == needle]
            candidates = [p for p in normalized_products if needle and (needle in p['name'].lower() or p['name'].lower() in needle)]
            if needle and len(candidates) < 8:
                fuzzy = []
                for product in normalized_products:
                    product_name = _hades_re.sub(r'[^a-z0-9]+', ' ', product['name'].lower()).strip()
                    score = _hades_difflib.SequenceMatcher(None, needle, product_name).ratio()
                    if score > 0.80 and product not in candidates:
                        fuzzy.append((score, product))
                candidates.extend(product for _score, product in sorted(fuzzy, reverse=True, key=lambda pair: pair[0]))
            candidates = candidates[:8]
            item['candidates'] = candidates
            if exact:
                item['product_id'] = exact[0]['product_id']
                item['resolution'] = 'EXACT'
        fingerprint = _hades_hashlib.sha256(data).hexdigest()
        review_items = [{key: item[key] for key in sorted(item) if key in {'name', 'line_total', 'resolution', 'product_id', 'candidates'}} for item in items]
        token = _review_token(fingerprint, review_items)
        return {'status': 'PREVIEW', 'filename': filename, 'mime': mime, 'ocr': decoded,
                'merchant': merchant, 'date': date, 'items': review_items, 'totals': totals,
                'requires_review': True, 'receipt_fingerprint': fingerprint,
                'review_token': token, 'canonical_target': 'Grocy stock intake',
                'lines': visible_lines,
                'writes': []}

    try:
        return JSONResponse(await _hades_asyncio.to_thread(_ocr))
    except Exception as exc:
        return JSONResponse({'status': 'FAILED', 'error': 'Receipt OCR preview failed.', 'detail': str(exc)}, status_code=502)


@app.post('/api/v1/hades/receipt/apply')
async def hades_receipt_apply(request: Request, user=Depends(get_verified_user)):
    """Apply only a signed, owner-confirmed receipt review to canonical Grocy."""
    import asyncio as _hades_asyncio
    import decimal as _hades_decimal
    import hashlib as _hades_hashlib
    import hmac as _hades_hmac
    import json as _hades_json
    import os as _hades_os
    import tempfile as _hades_tempfile
    import urllib.request as _hades_request

    def _review_secret():
        value = _hades_os.environ.get('WEBUI_SECRET_KEY', '')
        if not value:
            try:
                value = open('/app/backend/.webui_secret_key', encoding='utf-8').read().strip()
            except OSError:
                value = ''
        if not value:
            raise RuntimeError('Receipt review signing is unavailable.')
        return value.encode()

    def _review_token(fingerprint, items):
        payload = _hades_json.dumps({'fingerprint': fingerprint, 'items': items}, sort_keys=True, separators=(',', ':')).encode()
        return _hades_hmac.new(_review_secret(), payload, _hades_hashlib.sha256).hexdigest()

    def _grocy_key():
        path = _hades_os.environ.get('HADES_RECEIPT_GROCY_API_KEY_FILE', '').strip()
        if not path:
            return ''
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                value = handle.read().strip()
            return value if value and len(value) <= 4096 else ''
        except OSError:
            return ''

    def _grocy_json(method, path, body=None):
        key = _grocy_key()
        if not key:
            raise RuntimeError('Pantry review is unavailable because its protected service credential is not configured.')
        base = _hades_os.environ.get('HADES_RECEIPT_GROCY_URL', 'http://hades-grocy').rstrip('/')
        encoded = None if body is None else _hades_json.dumps(body).encode()
        headers = {'Accept': 'application/json', 'GROCY-API-KEY': key}
        if encoded is not None:
            headers['Content-Type'] = 'application/json'
        req = _hades_request.Request(f'{base}/api{path}', data=encoded, headers=headers, method=method)
        with _hades_request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8', 'replace')
            return _hades_json.loads(raw) if raw else {}

    def _fingerprint_status(fingerprint, mark=None):
        path = _hades_os.environ.get('HADES_RECEIPT_LEDGER_PATH', '/var/lib/hades-receipt/fingerprints.json')
        parent = _hades_os.path.dirname(path)
        if parent:
            _hades_os.makedirs(parent, mode=0o700, exist_ok=True)
        entries = {}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                value = _hades_json.load(handle)
            if isinstance(value, dict) and isinstance(value.get('fingerprints'), dict):
                entries = value['fingerprints']
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            raise RuntimeError('Receipt duplicate ledger is unavailable or malformed.')
        current = entries.get(fingerprint, {})
        status = current.get('status') if isinstance(current, dict) else None
        if mark is None:
            return status or 'NEW'
        entries[fingerprint] = {'status': mark}
        fd, temporary = _hades_tempfile.mkstemp(prefix='.receipt-ledger.', dir=parent or '.')
        try:
            _hades_os.fchmod(fd, 0o600)
            with _hades_os.fdopen(fd, 'w', encoding='utf-8') as handle:
                _hades_json.dump({'fingerprints': entries}, handle, sort_keys=True)
                handle.write('\n')
                handle.flush()
                _hades_os.fsync(handle.fileno())
            _hades_os.replace(temporary, path)
        finally:
            if _hades_os.path.exists(temporary):
                _hades_os.unlink(temporary)
        return mark

    owner_id = _hades_os.environ.get('HADES_RECEIPT_OWNER_USER_ID', '').strip()
    acceptance_ids = {value.strip() for value in _hades_os.environ.get('HADES_ACCEPTANCE_OWNER_USER_IDS', '').split(',') if value.strip()}
    owner_allowed = (str(getattr(user, 'id', '')) == owner_id and getattr(user, 'role', '') == 'admin') or str(getattr(user, 'id', '')) in acceptance_ids
    if not owner_allowed:
        raise HTTPException(status_code=403, detail='Receipt pantry updates are owner-only.')
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail='A receipt review is required.') from exc
    if not isinstance(body, dict) or body.get('confirm') is not True:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required before adding pantry items.')
    fingerprint = body.get('receipt_fingerprint')
    token = body.get('review_token')
    preview_items = body.get('preview_items')
    submitted_items = body.get('items')
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or not isinstance(preview_items, list) or not isinstance(submitted_items, list):
        raise HTTPException(status_code=400, detail='The receipt review is incomplete.')

    def _apply():
        expected = _review_token(fingerprint, preview_items)
        if not isinstance(token, str) or not _hades_hmac.compare_digest(token, expected):
            return {'status': 'FAILED', 'error': 'The review changed; create a fresh receipt preview before applying.'}
        status = _fingerprint_status(fingerprint)
        if status == 'APPLIED':
            return {'status': 'ALREADY APPLIED', 'writes_performed': False, 'canonical_target': 'Grocy stock intake'}
        if status == 'SUBMITTED':
            return {'status': 'OUTCOME UNKNOWN', 'writes_performed': False, 'error': 'This receipt was already submitted; reconcile Grocy before retrying.'}
        allowed = {}
        for item in preview_items:
            if isinstance(item, dict):
                allowed[str(item.get('name', ''))] = {int(candidate.get('product_id')) for candidate in item.get('candidates', []) if isinstance(candidate, dict) and candidate.get('product_id')}
                if item.get('product_id'):
                    allowed[str(item.get('name', ''))].add(int(item['product_id']))
        operations = []
        seen = set()
        for item in submitted_items:
            if not isinstance(item, dict):
                return {'status': 'FAILED', 'error': 'Every pantry item needs review.'}
            name = str(item.get('name', ''))
            try:
                product_id = int(item.get('product_id'))
                amount = _hades_decimal.Decimal(str(item.get('amount')))
            except (TypeError, ValueError, _hades_decimal.InvalidOperation):
                return {'status': 'FAILED', 'error': 'Each pantry item needs a valid product and positive quantity.'}
            if name not in allowed or product_id not in allowed[name] or product_id in seen or not amount.is_finite() or amount <= 0 or amount > 1000000:
                return {'status': 'FAILED', 'error': 'Each pantry item must match the reviewed receipt and use a positive bounded quantity.'}
            seen.add(product_id)
            operations.append((product_id, float(amount)))
        if not operations:
            return {'status': 'FAILED', 'error': 'At least one reviewed pantry item is required.'}
        _fingerprint_status(fingerprint, 'SUBMITTED')
        applied = []
        try:
            for product_id, amount in operations:
                _grocy_json('POST', f'/stock/products/{product_id}/add', {'amount': amount})
                applied.append({'product_id': product_id, 'amount': amount})
            readback = [_grocy_json('GET', f'/stock/products/{product_id}') for product_id, _ in operations]
            _fingerprint_status(fingerprint, 'APPLIED')
            return {'status': 'SUCCEEDED', 'writes_performed': True, 'canonical_target': 'Grocy stock intake', 'applied_items': applied, 'readback': readback}
        except Exception as exc:
            return {'status': 'OUTCOME UNKNOWN', 'writes_performed': bool(applied), 'error': 'Grocy was contacted; reconcile canonical pantry state before retrying.', 'applied_items': applied, 'detail': str(exc)}

    result = await _hades_asyncio.to_thread(_apply)
    return JSONResponse(result, status_code=200 if result.get('status') in {'SUCCEEDED', 'ALREADY APPLIED'} else 502)
'''

source = MAIN.read_text(encoding="utf-8")
if source.count(MARKER) != 1:
    raise SystemExit("expected exactly one Open WebUI chat endpoint marker")
if "hades_receipt_preview" in source:
    raise SystemExit("receipt OCR upload route is already installed")
MAIN.write_text(source.replace(MARKER, ROUTE + MARKER), encoding="utf-8")
print("PASS HADES owner-scoped receipt OCR preview route installed")
