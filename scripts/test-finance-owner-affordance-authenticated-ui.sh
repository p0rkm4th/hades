#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
suffix="$$"
image="${HADES_FINANCE_UI_IMAGE:-hades-open-webui:finance-access-$suffix}"
remove_image=1
if [[ -n "${HADES_FINANCE_UI_IMAGE:-}" ]]; then remove_image=0; fi
container="hades-finance-access-$suffix"
volume="hades-finance-access-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-finance-access.XXXXXX")
port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then docker logs --tail 50 "$container" >&2 2>/dev/null || true; fi
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  if ((remove_image)); then docker image rm "$image" >/dev/null 2>&1 || true; fi
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
for binary in docker curl python3 node; do command -v "$binary" >/dev/null; done
playwright_module=${HADES_PLAYWRIGHT_MODULE:-playwright}
HADES_PLAYWRIGHT_MODULE="$playwright_module" node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)'
printf 'Date,Payee,Amount\n2026-09-01,Synthetic Market,-4.29\n' >"$work/synthetic.csv"
if ((remove_image)); then docker build -f "$repo_dir/webui/Dockerfile" -t "$image" "$repo_dir"; fi
start_webui() {
  docker run -d --name "$container" -p "127.0.0.1:${port}:8080" \
    -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
    -e BYPASS_EMBEDDING_AND_RETRIEVAL=true -e HADES_FINANCE_OWNER_USER_ID="${owner_id:-}" \
    -v "$volume:/app/backend/data" "$image" >/dev/null
  for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -fsS "http://127.0.0.1:${port}/health" >/dev/null
}
docker volume create "$volume" >/dev/null
owner_id=''
start_webui
alpha=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signup" -H 'Content-Type: application/json' --data '{"name":"Synthetic Alpha","email":"alpha-finance@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha")
owner_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$alpha")
curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/add" -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data '{"name":"Synthetic Beta","email":"beta-finance@example.invalid","password":"Synthetic-Only-123!","role":"user"}' >/dev/null
docker rm -f "$container" >/dev/null
start_webui

cat >"$work/browser.js" <<'JS'
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE);
const base=process.env.BASE, csv=process.env.CSV;
async function login(email) {
 const auth=await fetch(`${base}/api/v1/auths/signin`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email,password:'Synthetic-Only-123!'})});
 if(!auth.ok) throw Error(`signin failed ${auth.status}`); const {token}=await auth.json();
 const browser=await chromium.launch({headless:true}); const context=await browser.newContext();
 await context.addCookies([{name:'token',value:token,url:`${base}/`}]); const page=await context.newPage();
 await page.goto(base,{waitUntil:'domcontentloaded'}); await page.waitForSelector('#chat-input',{timeout:30000});
 const welcome=page.getByRole('button',{name:/okay,\s*let.s go/i}); if(await welcome.count()) await welcome.first().click({force:true});
 return {browser,page};
}
async function attach(page) {
 const inputs=page.locator('input[type=file]'); if(!await inputs.count()) throw Error('file input missing');
 await inputs.last().setInputFiles(csv); await page.waitForFunction(()=>window.__hadesUploadedFileIds?.size>0,{timeout:15000});
}
(async()=>{
 const beta=await login('beta-finance@example.invalid');
 try {
   await attach(beta.page); await beta.page.waitForTimeout(500);
   const betaActionCount=await beta.page.locator('#hades-finance-csv-contextual-button').count();
   if(betaActionCount) {
     const diagnostic=await beta.page.evaluate(async()=>({tokenPresent:Boolean(localStorage.getItem('token')),tokenUser:(()=>{try{return JSON.parse(atob(localStorage.getItem('token').split('.')[1])).id}catch(_){return null}})(),access:await fetch('/api/v1/hades/finance/access').then(async r=>({status:r.status,body:(await r.text()).slice(0,240)}))}));
     throw Error(`household saw owner-only Review CSV action: ${JSON.stringify(diagnostic)}`);
   }
   const betaFileId=await beta.page.evaluate(()=>[...window.__hadesUploadedFileIds.values()].at(-1));
   if(!betaFileId) throw Error('synthetic household upload id was not observed');
   const betaStored=await beta.page.evaluate(async id=>({status:(await fetch(`/api/v1/files/${encodeURIComponent(id)}`)).status}),betaFileId);
   if(betaStored.status!==200) throw Error(`synthetic attached file was not available for the denial probe: ${JSON.stringify(betaStored)}`);
   const access=await beta.page.evaluate(async()=>{const r=await fetch('/api/v1/hades/finance/access');return {status:r.status,body:await r.json()}});
   if(access.status!==200||access.body.allowed!==false) throw Error(`household access policy mismatch: ${JSON.stringify(access)}`);
   const denied=await beta.page.evaluate(async()=>{const f=new FormData();f.append('file',new Blob(['Date,Amount\n2026-09-01,-1'],{type:'text/csv'}),'synthetic.csv');const r=await fetch('/api/v1/hades/finance/inspect',{method:'POST',body:f});return {status:r.status,body:await r.json()}});
   if(denied.status!==403) throw Error(`household inspect was not denied: ${JSON.stringify(denied)}`);
   const previewDenied=await beta.page.evaluate(async()=>{const f=new FormData();f.append('file',new Blob(['Date,Payee,Amount\n2026-09-01,Market,-1'],{type:'text/csv'}),'synthetic.csv');f.append('target_account_id','synthetic-account');f.append('mapping_json','{"date":"Date","payee":"Payee","amount":"Amount"}');const r=await fetch('/api/v1/hades/finance/preview',{method:'POST',body:f});return {status:r.status,body:await r.json()}});
   if(previewDenied.status!==403) throw Error(`household preview was not denied: ${JSON.stringify(previewDenied)}`);
   const betaStillStored=await beta.page.evaluate(async id=>({status:(await fetch(`/api/v1/files/${encodeURIComponent(id)}`)).status}),betaFileId);
   if(betaStillStored.status!==200) throw Error('household denial had a side effect on its unrelated attachment');
 } finally { await beta.browser.close(); }
 const alpha=await login('alpha-finance@example.invalid');
 try {
   await attach(alpha.page); await alpha.page.locator('#hades-finance-csv-contextual-button').waitFor({state:'visible',timeout:10000});
   const alphaFileId=await alpha.page.evaluate(()=>[...window.__hadesUploadedFileIds.values()].at(-1));
   if(!alphaFileId) throw Error('synthetic owner upload id was not observed');
   const alphaStored=await alpha.page.evaluate(async id=>{const r=await fetch(`/api/v1/files/${encodeURIComponent(id)}`);return {status:r.status,body:await r.json()};},alphaFileId);
   if(alphaStored.status!==200) throw Error(`synthetic owner upload was not available before review: ${JSON.stringify(alphaStored)}`);
   let syntheticPendingReads=0;
   await alpha.page.route(`**/api/v1/files/${encodeURIComponent(alphaFileId)}`,async route=>{
     if(route.request().method()==='GET'&&syntheticPendingReads<2){
       syntheticPendingReads+=1;
       const upstream=await route.fetch();
       const record=await upstream.json();
       record.data={...(record.data||{}),status:'pending'};
       return route.fulfill({response:upstream,contentType:'application/json',body:JSON.stringify(record)});
     }
     return route.continue();
   });
   const access=await alpha.page.evaluate(async()=>{const r=await fetch('/api/v1/hades/finance/access');return {status:r.status,body:await r.json()}});
   if(access.status!==200||access.body.allowed!==true) throw Error(`owner access policy mismatch: ${JSON.stringify(access)}`);
   await alpha.page.locator('#hades-finance-csv-contextual-button').click();
   const modal=alpha.page.locator('#hades-finance-csv-modal');
   await modal.waitFor({state:'visible',timeout:5000});
   const alphaDeleted=await alpha.page.evaluate(async id=>({status:(await fetch(`/api/v1/files/${encodeURIComponent(id)}`)).status}),alphaFileId);
   if(alphaDeleted.status!==404) throw Error(`Open WebUI retained the statement after starting finance review: ${JSON.stringify(alphaDeleted)}; dialog=${await modal.innerText()}`);
   if(syntheticPendingReads!==2) throw Error(`finance review did not wait for the two simulated processing states: ${syntheticPendingReads}`);
   await modal.getByRole('button',{name:'Review statement',exact:true}).click();
   await alpha.page.getByText(/I found 1 transaction rows in synthetic\.csv/).waitFor({timeout:10000});
   const reviewed=await modal.innerText();
   if(!reviewed.includes('2026-09-01')||! /read-only review/i.test(reviewed)||! /nothing is imported/i.test(reviewed)) throw Error(`owner synthetic statement was not accurately described as preview-only: ${reviewed}`);
   if(! /nothing is imported from this screen/i.test(reviewed)) throw Error(`owner inspection did not preserve the no-import boundary: ${reviewed}`);
 } finally { await alpha.browser.close(); }
 console.log('PASS synthetic household cannot see or invoke owner finance review');
 console.log('PASS synthetic owner sees and uses contextual CSV inspection; no import is performed');
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
JS
BASE="http://127.0.0.1:${port}" CSV="$work/synthetic.csv" HADES_PLAYWRIGHT_MODULE="$playwright_module" node "$work/browser.js"
