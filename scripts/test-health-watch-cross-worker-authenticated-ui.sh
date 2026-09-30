#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
suffix=$$
name="hades-hw-race-$suffix"; volume="hades-hw-race-$suffix"
image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-hw-ui.XXXXXX")
pa=${HADES_HW_UI_GATEWAY_A_PORT:-18941}; pb=${HADES_HW_UI_GATEWAY_B_PORT:-18942}; pp=${HADES_HW_UI_PROXY_PORT:-18943}; pm=${HADES_HW_UI_MODEL_PORT:-18944}; pw=${HADES_HW_UI_WEBUI_PORT:-18940}; pc=${HADES_HW_UI_PROXMOX_PORT:-18945}
ka="synthetic-a-$suffix"; kb="synthetic-b-$suffix"; ga=''; gb=''; proxy_pid=''; model_pid=''; proxmox_pid=''; step=preflight
cleanup() { local s=$?; trap - EXIT; if ((s)); then echo "FAIL at $step" >&2; tail -n 35 "$work"/*.log >&2 2>/dev/null || true; fi
  for p in "$ga" "$gb" "$proxy_pid" "$model_pid" "$proxmox_pid"; do [[ -z $p ]] || { kill "$p" 2>/dev/null || true; wait "$p" 2>/dev/null || true; }; done
  docker rm -f "$name" >/dev/null 2>&1 || true; docker volume rm "$volume" >/dev/null 2>&1 || true
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true; exit "$s"; }
trap cleanup EXIT; trap 'exit 130' INT TERM
for x in docker hermes curl node python3; do command -v "$x" >/dev/null; done
docker image inspect "$image" >/dev/null
for p in "$pa" "$pb" "$pp" "$pm" "$pw" "$pc"; do (echo >/dev/tcp/127.0.0.1/$p) >/dev/null 2>&1 && { echo "FAIL port occupied: $p"; exit 2; } || true; done
bridge=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' | head -1)
bin=$(readlink -f "$(command -v hermes)"); hp="$(dirname "$bin")/python3.11"; [[ -x $hp ]]
src=$(cd "$(dirname "$hp")/../.." && pwd); mkdir -m 700 "$work/home-a" "$work/home-b" "$work/hermes"
step='start deterministic local model responder'
cat >"$work/model.py" <<'PY'
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,sys,time
port,log=sys.argv[1:]; port=int(port); model='synthetic-health-model'
class H(BaseHTTPRequestHandler):
 def log_message(self,*_): pass
 def do_GET(self):
  data=json.dumps({'data':[{'id':model,'object':'model','owned_by':'synthetic'}]}).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
 def do_POST(self):
  payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))); text=' '.join(str(m.get('content','')) for m in payload.get('messages',[])).casefold()
  user_turns=[str(m.get('content','')) for m in payload.get('messages',[]) if m.get('role')=='user']; latest_user=user_turns[-1].casefold() if user_turns else ''
  if 'generate a concise title' in text: kind,reply='title','{"title":"Health Watch"}'
  elif 'follow-up questions' in text: kind,reply='suggestions','[]'
  elif 'broad tags' in text: kind,reply='tags','{"tags":[]}'
  elif latest_user.strip()=='create it' or latest_user.startswith('can you spin up a minecraft server'): kind,reply='unexpected_provisioning_inference','UNEXPECTED_PROVISIONING_MODEL_INVOCATION'
  else: kind,reply='unexpected_inference','UNEXPECTED_MODEL_INVOCATION'
  with open(log,'a') as f:f.write(json.dumps({'kind':kind})+'\n')
  now=int(time.time()); ident='synthetic-health-model-call'; self.send_response(200)
  if payload.get('stream'):
   self.send_header('Content-Type','text/event-stream'); self.end_headers()
   chunks=[{'id':ident,'object':'chat.completion.chunk','created':now,'model':model,'choices':[{'index':0,'delta':{'role':'assistant','content':reply},'finish_reason':None}]},{'id':ident,'object':'chat.completion.chunk','created':now,'model':model,'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
   for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode()); self.wfile.flush()
   self.wfile.write(b'data: [DONE]\n\n'); self.wfile.flush()
  else:
   body={'id':ident,'object':'chat.completion','created':now,'model':model,'choices':[{'index':0,'message':{'role':'assistant','content':reply},'finish_reason':'stop'}]}; data=json.dumps(body).encode(); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer(('127.0.0.1',port),H).serve_forever()
PY
python3 "$work/model.py" "$pm" "$work/model.log" >"$work/model.out" 2>&1 & model_pid=$!
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$pm/v1/models" >/dev/null 2>&1 && break; sleep .1; done
curl -fsS "http://127.0.0.1:$pm/v1/models" >/dev/null
step='start loopback synthetic Proxmox API'
cat >"$work/proxmox.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, sys

port, log = sys.argv[1], sys.argv[2]
expected_auth = 'PVEAPIToken=synthetic@pve!hades-test=synthetic-token'
state = {'created': False, 'started': False}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def respond(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        path = self.path.split('?', 1)[0]
        if self.command == 'GET' and path == '/healthz':
            return self.respond(200, {'status': 'READY'})
        with open(log, 'a') as out:
            out.write(json.dumps({'method': self.command, 'path': path}) + '\n')
        if self.headers.get('Authorization') != expected_auth:
            return self.respond(401, {'errors': 'synthetic authorization denied'})
        if self.command == 'GET' and path == '/api2/json/cluster/nextid':
            return self.respond(200, {'data': '9901'})
        if self.command == 'POST' and path == '/api2/json/nodes/SyntheticNode/qemu/9001/clone':
            state['created'] = True
            return self.respond(200, {'data': 'UPID:SyntheticNode:clone'})
        if self.command == 'GET' and path in {
            '/api2/json/nodes/SyntheticNode/tasks/UPID:SyntheticNode:clone/status',
            '/api2/json/nodes/SyntheticNode/tasks/UPID:SyntheticNode:start/status',
        }:
            return self.respond(200, {'data': {'status': 'stopped', 'exitstatus': 'OK'}})
        if self.command == 'PUT' and path == '/api2/json/nodes/SyntheticNode/qemu/9901/config':
            return self.respond(200, {'data': None})
        if self.command == 'PUT' and path == '/api2/json/nodes/SyntheticNode/qemu/9901/resize':
            return self.respond(200, {'data': None})
        if self.command == 'POST' and path == '/api2/json/nodes/SyntheticNode/qemu/9901/status/start':
            state['started'] = True
            return self.respond(200, {'data': 'UPID:SyntheticNode:start'})
        if self.command == 'GET' and path == '/api2/json/nodes/SyntheticNode/qemu/9901/status/current':
            status = 'running' if state['created'] and state['started'] else 'stopped'
            return self.respond(200, {'data': {'status': status}})
        return self.respond(404, {'errors': 'unexpected synthetic route'})

    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch

ThreadingHTTPServer(('127.0.0.1', int(port)), Handler).serve_forever()
PY
python3 "$work/proxmox.py" "$pc" "$work/proxmox.log" >"$work/proxmox.out" 2>&1 & proxmox_pid=$!
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:$pc/healthz" >/dev/null 2>&1 && break; sleep .1; done
python3 - "$work/proxmox-token" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]); p.write_text('synthetic-token\n', encoding='utf-8'); p.chmod(0o600)
PY
step='start synthetic Open WebUI'; docker volume create "$volume" >/dev/null
docker run -d --name "$name" --add-host host.docker.internal:host-gateway -p "127.0.0.1:$pw:8080" -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama -v "$volume:/app/backend/data" "$image" >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:$pw/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:$pw/health" >/dev/null
step='create synthetic identities'; root="http://127.0.0.1:$pw"
alpha=$(curl -fsS -X POST "$root/api/v1/auths/signup" -H 'Content-Type: application/json' --data '{"name":"Alpha","email":"alpha-hw@example.invalid","password":"Synthetic-Only-123!"}')
at=$(python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])' <<<"$alpha"); aid=$(python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])' <<<"$alpha")
beta=$(curl -fsS -X POST "$root/api/v1/auths/add" -H "Authorization: Bearer $at" -H 'Content-Type: application/json' --data '{"name":"Beta","email":"beta-hw@example.invalid","password":"Synthetic-Only-123!","role":"user"}')
bid=$(python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])' <<<"$beta"); state="$work/state.sqlite"
PYTHONPATH="$repo_dir" python3 - "$state" "$aid" <<'PY'
import sys
from integrations.automation import HealthSource,HealthWatchService,HealthWatchSpec,HealthWatchStore
s=HealthWatchStore(sys.argv[1]); w=s.create(HealthWatchSpec('synthetic-hw-watch',sys.argv[2],'hades-core','HADES Core Watch',10),'synthetic-seed',sys.argv[2]); assert w['automation_id']=='synthetic-hw-watch'
PY
step='launch two Hermes gateways'; for profile in hades-worker-a hades-worker-b; do HERMES_HOME="$work/hermes" hermes profile create "$profile" --no-alias --no-skills >/dev/null; done
cat >"$work/hermes/profiles/hades-worker-a/config.yaml" <<YAML
model:
  default: synthetic-health-a
  provider: custom
  base_url: http://127.0.0.1:$pm/v1
YAML
cat >"$work/hermes/profiles/hades-worker-b/config.yaml" <<YAML
model:
  default: synthetic-health-b
  provider: custom
  base_url: http://127.0.0.1:$pm/v1
YAML
common=("HERMES_HOME=$work/hermes" "HADES_HERMES_EXECUTABLE=$bin" "PYTHONPATH=$repo_dir/hermes:$repo_dir:$src" "HADES_OWNER_SUBJECT_IDS=$aid" "HADES_SELF_SERVICE_SHARE_SUBJECTS=household-a:$bid" "HADES_EPSILON_STATE_FILE=$state" "HADES_SELF_SERVICE_REGISTRY_FILE=$work/workloads.json" "HADES_PROXMOX_CONTROL_URL=http://127.0.0.1:$pc/api2/json" HADES_PROXMOX_CONTROL_TOKEN_ID='synthetic@pve!hades-test' "HADES_PROXMOX_CONTROL_TOKEN_FILE=$work/proxmox-token" HADES_PROXMOX_CONTROL_NODES=SyntheticNode HADES_PROXMOX_TEMPLATE_MAP=minecraft:9001 'HADES_EPSILON_HEALTH_SOURCES_JSON={"hades-core":{"display_name":"HADES Core","url":"http://127.0.0.1:9/health"}}' OPENAI_API_KEY=synthetic-unused HERMES_ACCEPT_HOOKS=1 API_SERVER_ENABLED=true)
env "${common[@]}" "HOME=$work/home-a" "API_SERVER_KEY=$ka" "API_SERVER_HOST=$bridge" "API_SERVER_PORT=$pa" hermes -p hades-worker-a gateway run -v >"$work/a.log" 2>&1 & ga=$!
env "${common[@]}" "HOME=$work/home-b" "API_SERVER_KEY=$kb" "API_SERVER_HOST=$bridge" "API_SERVER_PORT=$pb" hermes -p hades-worker-b gateway run -v >"$work/b.log" 2>&1 & gb=$!
for p in "$pa" "$pb"; do ok=0; for _ in $(seq 1 90); do curl -fsS "http://$bridge:$p/health" >/dev/null 2>&1 && { ok=1; break; }; sleep 1; done; ((ok)) || { echo "gateway $p unavailable"; exit 1; }; done
ma=$(curl -fsS -H "Authorization: Bearer $ka" "http://$bridge:$pa/v1/models" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
mb=$(curl -fsS -H "Authorization: Bearer $kb" "http://$bridge:$pb/v1/models" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])'); [[ $ma != "$mb" ]]
step='starting deterministic in-chat worker router'
cat >"$work/proxy.py" <<'PY'
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import http.client,json,sys
port,host,pa,pb,ka,kb,ma,mb,log=sys.argv[1:]; port=int(port); pa=int(pa); pb=int(pb)
class H(BaseHTTPRequestHandler):
 def log_message(self,*_): pass
 def do_GET(self):
  body=json.dumps({'object':'list','data':[{'id':'hades-cross-worker','object':'model','owned_by':'synthetic'}]}).encode()
  self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
 def do_POST(self):
  raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
  if self.path!='/v1/chat/completions': self.send_error(404); return
  payload=json.loads(raw); users=[m.get('content','') for m in payload.get('messages',[]) if m.get('role')=='user']; latest=str(users[-1] if users else '').casefold()
  if latest.startswith('share hades core watch'): label,target,key,model,turn='B',pb,kb,mb,'share'
  elif latest.strip()=='yes.': label,target,key,model,turn='A',pa,ka,ma,'confirm'
  elif latest.startswith('can you spin up a minecraft server') and ('port/ip' in latest or 'firewall' in latest): label,target,key,model,turn='A',pa,ka,ma,'provision-request'
  elif latest.strip()=='perfect, continue' and any('port/ip' in str(text).casefold() or 'firewall' in str(text).casefold() for text in users[:-1]): label,target,key,model,turn='B',pb,kb,mb,'provision-continue'
  elif latest.startswith('can you spin up a minecraft server'): label,target,key,model,turn='A',pa,ka,ma,'provision-request'
  elif latest.strip()=='perfect, continue': label,target,key,model,turn='B',pb,kb,mb,'provision-continue'
  elif latest.strip()=='create it': label,target,key,model,turn='A',pa,ka,ma,'provision-confirm'
  elif latest.startswith('monitor hades core'): label,target,key,model,turn='A',pa,ka,ma,'create'
  else: label,target,key,model,turn='A',pa,ka,ma,'aux'
  payload['model']=model; encoded=json.dumps(payload).encode()
  with open(log,'a') as out: out.write(json.dumps({'worker':label,'turn':turn})+'\n')
  conn=http.client.HTTPConnection(host,target,timeout=90)
  headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':self.headers.get('Accept','text/event-stream')}
  session=self.headers.get('X-Hermes-Session-Key')
  if session: headers['X-Hermes-Session-Key']=session
  conn.request('POST','/v1/chat/completions',body=encoded,headers=headers); response=conn.getresponse(); data=response.read()
  self.send_response(response.status)
  for name,value in response.getheaders():
   if name.lower() not in ('transfer-encoding','connection','content-length'): self.send_header(name,value)
  self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); conn.close()
ThreadingHTTPServer(('0.0.0.0',port),H).serve_forever()
PY
python3 "$work/proxy.py" "$pp" "$bridge" "$pa" "$pb" "$ka" "$kb" "$ma" "$mb" "$work/proxy.log" >"$work/proxy.out" 2>&1 & proxy_pid=$!
for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:$pp/v1/models" >/dev/null 2>&1 && break; sleep .1; done
curl -fsS "http://127.0.0.1:$pp/v1/models" >/dev/null
step='configure authenticated model access'
python3 - "$pw" "$at" "$pp" "$aid" <<'PY'
import json,sys,urllib.request
port,token,proxy,uid=sys.argv[1:]; base=f'http://127.0.0.1:{port}'
def post(path,obj):
 data=json.dumps(obj).encode(); req=urllib.request.Request(base+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req) as response: response.read()
post('/openai/config/update',{'ENABLE_OPENAI_API':True,'OPENAI_API_BASE_URLS':[f'http://host.docker.internal:{proxy}/v1'],'OPENAI_API_KEYS':['synthetic-router'],'OPENAI_API_CONFIGS':{'0':{'headers':{'X-Hermes-Session-Key':'hades-user-{{USER_ID}}'}}}})
mid='hades-cross-worker'; post('/api/v1/models/model/access/update',{'id':mid,'name':mid,'access_grants':[{'principal_type':'user','principal_id':uid,'permission':'read'}]})
req=urllib.request.Request(base+'/openai/models',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req) as response: visible=json.load(response).get('data',[])
ids={str(row.get('id','')) for row in visible}
if mid not in ids: raise SystemExit('synthetic cross-worker model is not visible to authenticated Alpha: '+repr(sorted(ids)))
PY
step='authenticated UI cross-worker confirmation'; report="$work/report.json"
HADES_HW_UI_BASE_URL="$root" HADES_HW_UI_EMAIL=alpha-hw@example.invalid HADES_HW_UI_PASSWORD='Synthetic-Only-123!' HADES_HW_UI_MODEL_A=hades-cross-worker HADES_HW_UI_MODEL_B=hades-cross-worker HADES_HW_UI_REPORT="$report" node "$repo_dir/scripts/dom-health-watch-cross-worker-authenticated.js"
step='canonical state verification'
PYTHONPATH="$repo_dir" python3 - "$state" "$aid" "$bid" <<'PY'
import sys
from integrations.automation import HealthWatchStore
w=HealthWatchStore(sys.argv[1]).list_all(); assert len(w)==1 and w[0]['owner']==sys.argv[2] and tuple(w[0]['shared_subjects'])==(sys.argv[3],),w
print('PASS one original synthetic watch is shared with Beta; no stale duplicate')
PY
python3 - "$work/proxy.log" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1])]
routes=[(x['turn'],x['worker']) for x in rows if x['turn'] in ('create','share','confirm')]
assert routes==[('create','A'),('share','B'),('confirm','A')],routes
print('PASS authenticated turns traversed Hermes workers A, B, A through one model endpoint')
provision=[(x['turn'],x['worker']) for x in rows if x['turn'].startswith('provision-')]
assert provision==[('provision-request','A'),('provision-continue','B'),('provision-confirm','A')],provision
print('PASS Minecraft preview, continuation, and explicit confirmation recovered durable state across Hermes workers A to B to A')
PY
PYTHONPATH="$repo_dir" python3 - "$work/proxmox.log" "$work/workloads.json" "$aid" <<'PY'
import json,sys
from integrations.self_service.registry import WorkloadRegistry
calls=[json.loads(line) for line in open(sys.argv[1])]
expected=[
 ('GET','/api2/json/cluster/nextid'),
 ('POST','/api2/json/nodes/SyntheticNode/qemu/9001/clone'),
 ('GET','/api2/json/nodes/SyntheticNode/tasks/UPID:SyntheticNode:clone/status'),
 ('PUT','/api2/json/nodes/SyntheticNode/qemu/9901/config'),
 ('PUT','/api2/json/nodes/SyntheticNode/qemu/9901/resize'),
 ('POST','/api2/json/nodes/SyntheticNode/qemu/9901/status/start'),
 ('GET','/api2/json/nodes/SyntheticNode/tasks/UPID:SyntheticNode:start/status'),
 ('GET','/api2/json/nodes/SyntheticNode/qemu/9901/status/current'),
]
assert [(row['method'],row['path']) for row in calls]==expected,calls
registry=WorkloadRegistry(sys.argv[2]).list_for(sys.argv[3])
assert len(registry)==1 and registry[0]['vmid']==9901 and registry[0]['template']=='minecraft',registry
print('PASS explicit owner confirmation used only the loopback Proxmox fixture and persisted synthetic workload ownership')
PY
python3 - "$work/model.log" <<'PY'
import json,sys
rows=[json.loads(line) for line in open(sys.argv[1])]
assert not any(row.get('kind')=='unexpected_provisioning_inference' for row in rows),rows
print('PASS Minecraft request, continuation, and confirmation triggered no model inference')
PY
install -m 600 "$report" "${HADES_HW_UI_REPORT_OUT:-/tmp/hades-health-watch-cross-worker-ui-$$.json}"
echo 'PASS authenticated cross-worker Health Watch acceptance'
