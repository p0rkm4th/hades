"""Add the HADES owner-scoped, preview-only finance CSV endpoint to Open WebUI."""

from pathlib import Path


MAIN = Path("/app/backend/open_webui/main.py")
MARKER = "\n\n##################################\n#\n# Chat Endpoints"
ROUTE = r'''

# HADES finance statement inspection: same-origin, owner-scoped, write-free.
@app.post('/api/v1/hades/finance/inspect')
async def hades_finance_statement_inspect(request: Request, user=Depends(get_verified_user)):
    """Identify a statement and suggest next steps without requiring an account ID."""
    import base64 as _hades_base64
    import sys as _hades_sys

    owner_id = os.environ.get('HADES_FINANCE_OWNER_USER_ID', '').strip()
    acceptance_ids = {value.strip() for value in os.environ.get('HADES_ACCEPTANCE_OWNER_USER_IDS', '').split(',') if value.strip()}
    owner_allowed = (str(getattr(user, 'id', '')) == owner_id and getattr(user, 'role', '') == 'admin') or str(getattr(user, 'id', '')) in acceptance_ids
    if not owner_allowed:
        raise HTTPException(status_code=403, detail='Finance statement inspection is owner-only.')
    form = await request.form(max_part_size=10 * 1024 * 1024)
    upload = form.get('file')
    if upload is None or not hasattr(upload, 'read'):
        raise HTTPException(status_code=400, detail='A financial statement file is required.')
    filename = str(getattr(upload, 'filename', '') or '')
    data = await upload.read()
    if not isinstance(data, bytes) or not data:
        raise HTTPException(status_code=400, detail='The statement file is empty.')
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='The statement file exceeds the 10 MiB limit.')
    finance_path = '/opt/hades/finance-import'
    if finance_path not in _hades_sys.path:
        _hades_sys.path.insert(0, finance_path)
    from service import inspect_file as _hades_inspect_file
    return JSONResponse(_hades_inspect_file(_hades_base64.b64encode(data).decode('ascii'), filename))

# HADES finance CSV upload: same-origin, owner-scoped, preview-only.
@app.post('/api/v1/hades/finance/preview')
async def hades_finance_csv_preview(request: Request, user=Depends(get_verified_user)):
    """Preview one inline CSV without retaining it or writing Actual Budget."""
    import base64 as _hades_base64
    import sys as _hades_sys

    owner_id = os.environ.get('HADES_FINANCE_OWNER_USER_ID', '').strip()
    acceptance_ids = {value.strip() for value in os.environ.get('HADES_ACCEPTANCE_OWNER_USER_IDS', '').split(',') if value.strip()}
    owner_allowed = (str(getattr(user, 'id', '')) == owner_id and getattr(user, 'role', '') == 'admin') or str(getattr(user, 'id', '')) in acceptance_ids
    if not owner_allowed:
        raise HTTPException(status_code=403, detail='Finance CSV preview is owner-only.')

    form = await request.form(max_part_size=10 * 1024 * 1024)
    upload = form.get('file')
    if upload is None or not hasattr(upload, 'read'):
        raise HTTPException(status_code=400, detail='A CSV file is required.')
    filename = str(getattr(upload, 'filename', '') or '')
    if not filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail='Only CSV uploads are accepted.')
    data = await upload.read()
    if not isinstance(data, bytes) or not data:
        raise HTTPException(status_code=400, detail='The CSV file is empty.')
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='The CSV file exceeds the 10 MiB preview limit.')

    finance_path = '/opt/hades/finance-import'
    if finance_path not in _hades_sys.path:
        _hades_sys.path.insert(0, finance_path)
    from service import preview_file as _hades_preview_file

    result = _hades_preview_file(
        _hades_base64.b64encode(data).decode('ascii'),
        filename,
        str(form.get('target_account_id', '') or ''),
        str(form.get('mapping_json', '{}') or '{}'),
        str(form.get('existing_transactions_json', '[]') or '[]'),
    )
    return JSONResponse(result)
'''

source = MAIN.read_text(encoding="utf-8")
if source.count(MARKER) != 1:
    raise SystemExit("expected exactly one Open WebUI chat endpoint marker")
if "hades_finance_csv_preview" in source:
    raise SystemExit("finance upload route is already installed")
MAIN.write_text(source.replace(MARKER, ROUTE + MARKER), encoding="utf-8")
print("PASS HADES owner-scoped finance CSV preview route installed")
