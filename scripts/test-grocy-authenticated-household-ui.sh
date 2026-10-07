#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Authenticated household acceptance against a synthetic canonical Grocy API.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
hermes_overlay_dir=${HADES_HERMES_OVERLAY_DIR:-$repo_dir/hermes}
[[ -f "$hermes_overlay_dir/sitecustomize.py" ]] || { echo "FAIL Hermes overlay is missing sitecustomize.py: $hermes_overlay_dir" >&2; exit 2; }
webui_image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
webui_name="hades-grocy-ui-webui-$suffix"
webui_volume="hades-grocy-ui-webui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-grocy-ui.XXXXXX")
webui_port=${HADES_GROCY_UI_WEBUI_PORT:-18886}
gateway_port=${HADES_GROCY_UI_GATEWAY_PORT:-18887}
api_key="synthetic-hades-grocy-ui-$suffix"
gateway_pid=''
grocy_pid=''
model_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL authenticated Grocy household UI at step '$step'" >&2
    [[ -f "$work/hermes.log" ]] && tail -n 60 "$work/hermes.log" >&2 || true
    [[ -f "$work/grocy-requests.jsonl" ]] && cat "$work/grocy-requests.jsonl" >&2 || true
    if [[ -n ${HADES_GROCY_UI_DEBUG_DIR:-} ]]; then
      mkdir -m 700 -p "$HADES_GROCY_UI_DEBUG_DIR"
      [[ ! -f "$work/hermes.log" ]] || install -m 600 "$work/hermes.log" "$HADES_GROCY_UI_DEBUG_DIR/hermes.log"
      [[ ! -f "$work/grocy-requests.jsonl" ]] || install -m 600 "$work/grocy-requests.jsonl" "$HADES_GROCY_UI_DEBUG_DIR/grocy-requests.jsonl"
      [[ ! -f "$work/model-calls.jsonl" ]] || install -m 600 "$work/model-calls.jsonl" "$HADES_GROCY_UI_DEBUG_DIR/model-calls.jsonl"
      docker logs "$webui_name" >"$HADES_GROCY_UI_DEBUG_DIR/open-webui.log" 2>&1 || true
      local request_dump
      request_dump=$(find "$work/hermes" -type f -name 'request_dump*.json' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
      [[ -z "$request_dump" ]] || install -m 600 "$request_dump" "$HADES_GROCY_UI_DEBUG_DIR/$(basename "$request_dump")"
      echo "Synthetic failure diagnostics saved to $HADES_GROCY_UI_DEBUG_DIR" >&2
    fi
  fi
  if [[ -n "$gateway_pid" ]]; then kill "$gateway_pid" >/dev/null 2>&1 || true; wait "$gateway_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$grocy_pid" ]]; then kill "$grocy_pid" >/dev/null 2>&1 || true; wait "$grocy_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$model_pid" ]]; then kill "$model_pid" >/dev/null 2>&1 || true; wait "$model_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$webui_name" >/dev/null 2>&1 || true
  docker volume rm "$webui_volume" >/dev/null 2>&1 || true
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for binary in docker hermes node curl python3; do command -v "$binary" >/dev/null; done
export HADES_PLAYWRIGHT_MODULE=${HADES_PLAYWRIGHT_MODULE:-playwright}; node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)' >/dev/null 2>&1 || { echo 'FAIL local Playwright dependency is unavailable' >&2; exit 2; }
docker image inspect "$webui_image" >/dev/null
for port in "$webui_port" "$gateway_port"; do
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then echo "FAIL occupied test port: $port" >&2; exit 2; fi
done
docker_gateway=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' | head -n1)
[[ "$docker_gateway" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo 'FAIL Docker bridge gateway unavailable' >&2; exit 2; }
chmod 700 "$work"
export HADES_SYNTHETIC_GROCY_FAILURE_FILE="$work/grocy-unavailable"
touch "$work/grocy-requests.jsonl" "$work/grocy-audit.jsonl" "$work/model-calls.jsonl" "$work/composition-mcp.jsonl"
export HADES_GROCY_UI_COMPOSITION_CALLS_FILE="$work/composition-mcp.jsonl"

step='starting synthetic Grocy authority'
python3 "$repo_dir/scripts/synthetic-grocy-api.py" "$docker_gateway" "$work/grocy.port" "$work/grocy-requests.jsonl" >"$work/grocy.log" 2>&1 &
grocy_pid=$!
for _ in $(seq 1 50); do [[ -s "$work/grocy.port" ]] && break; kill -0 "$grocy_pid" 2>/dev/null || { cat "$work/grocy.log" >&2; exit 1; }; sleep 0.1; done
[[ -s "$work/grocy.port" ]] || { echo 'FAIL synthetic Grocy API did not bind' >&2; exit 1; }
grocy_url="http://${docker_gateway}:$(cat "$work/grocy.port")"

step='starting deterministic Hermes auxiliary responder'
cat >"$work/model.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, re, sys, threading, time
import os
port_file, calls_file = map(Path, sys.argv[1:])
scope_probe = os.environ.get('HADES_GROCY_UI_RECIPE_SCOPE_PROBE') == '1'
recipe_authoring = os.environ.get('HADES_GROCY_UI_RECIPE_AUTHORING') == '1'
recipe_web_compose = os.environ.get('HADES_GROCY_UI_RECIPE_WEB_COMPOSE') == '1'
calls_lock = threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        if self.path.rstrip('/') != '/v1/models': self.send_response(404); self.end_headers(); return
        body=json.dumps({'data':[{'id':'synthetic-no-call','object':'model','owned_by':'synthetic'}]}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        if self.path != '/v1/chat/completions': self.send_response(404); self.end_headers(); return
        user_messages=[str(row.get('content','')) for row in payload.get('messages',[]) if row.get('role')=='user']
        text='\n'.join(user_messages)
        current_user=user_messages[-1] if user_messages else ''
        assistant_messages=[str(row.get('content','')) for row in payload.get('messages',[]) if row.get('role')=='assistant']
        prior_assistant='\n'.join(assistant_messages)
        scope_turn = scope_probe and 'scope-probe' in current_user
        tool_messages=[row for row in payload.get('messages',[]) if row.get('role')=='tool']
        prior_search=any(call.get('function',{}).get('name')=='tool_search' for row in payload.get('messages',[]) for call in row.get('tool_calls',[]))
        prior_raw_attempt=any(call.get('function',{}).get('name')=='tool_call' for row in payload.get('messages',[]) for call in row.get('tool_calls',[]))
        household_owner_tools_exposed=None
        authoring_steps={
            'Please add my new recipe HADES Synthetic Authoring Soup':'create',
            'For HADES Synthetic Authoring Soup, remove the eggs ingredient':'remove',
            'Restore 2 eggs in the recipe HADES Synthetic Authoring Soup':'restore',
            'Can I make HADES Synthetic Authoring Soup':'fulfillment',
            "Add only what's missing for HADES Synthetic Authoring Soup":'shopping',
            'Please create a new recipe Beta Unauthorized Soup':'household_attempt',
        }
        authoring_step=next((step for marker,step in authoring_steps.items() if current_user.strip().startswith(marker)),None) if recipe_authoring else None
        tool_result=bool(payload.get('messages') and payload['messages'][-1].get('role')=='tool')
        compose_prompt = recipe_web_compose and current_user.strip().startswith('Find a quick recipe from a recipe website using milk and rice')
        compose_calls = [call.get('function',{}).get('name','') for row in payload.get('messages',[]) for call in row.get('tool_calls',[])]
        compose_tools = [row.get('function',{}).get('name','') for row in payload.get('tools',[]) if isinstance(row,dict)]
        if 'Generate a concise title' in text: kind, reply='title', '{"title":"Household groceries"}'
        elif 'Suggest ' in text and 'follow-up questions' in text: kind, reply='suggestions', '[]'
        elif 'broad tags' in text: kind, reply='tags', '{"tags":[]}'
        elif current_user.strip()=='No, I meant put the milk in the recipe instead.':
            prior_action_ack=any(
                'added milk to the shared shopping list and verified it.' in message.casefold()
                for message in assistant_messages
            )
            kind='post_mutation_correction' if prior_action_ack else 'post_mutation_correction_context_probe'
            reply=("I already added milk to the shared shopping list and verified it. "
                   "I haven't changed any recipe. Only the owner can change saved recipes. "
                   "I can remove milk from the list if you'd like.") if prior_action_ack else (
                   "I haven't changed any recipe. Only the owner can change saved recipes. "
                   "I can remove milk from the list if you'd like.")
        elif compose_prompt and not any(name.endswith('stock_overview_tool') for name in compose_calls):
            stock_name=next((name for name in compose_tools if name.endswith('stock_overview_tool')),None)
            research_name=next((name for name in compose_tools if name.endswith('public_research')),None)
            write_names=[name for name in compose_tools if any(term in name.lower() for term in ('shopping_list_add','recipe_create','recipe_update','add_to_shopping'))]
            if not stock_name or not research_name or write_names:
                raise AssertionError({'compound_read_catalog_missing_or_writable':compose_tools,'write_tools':write_names})
            kind, reply='recipe_web_compose_stock', ''
            call={'id':'call-synthetic-compose-stock','type':'function','function':{'name':stock_name,'arguments':'{}'}}
        elif compose_prompt and not any(name.endswith('public_research') for name in compose_calls):
            if not tool_messages or 'milk' not in str(tool_messages[-1].get('content','')).lower() or 'rice' not in str(tool_messages[-1].get('content','')).lower():
                raise AssertionError({'canonical_stock_result_missing_before_research':tool_messages})
            research_name=next((name for name in compose_tools if name.endswith('public_research')),None)
            if not research_name:
                raise AssertionError({'public_research_missing_after_stock_read':compose_tools})
            kind, reply='recipe_web_compose_research', ''
            call={'id':'call-synthetic-compose-research','type':'function','function':{'name':research_name,'arguments':json.dumps({'query':'quick milk rice recipe under 30 minutes','subject_class':'public_topic','research_scope':'standard'})}}
        elif compose_prompt:
            if not tool_messages:
                raise AssertionError({'public_recipe_evidence_missing':tool_messages})
            evidence_text=str(tool_messages[-1].get('content',''))
            if '\n\n' in evidence_text:
                evidence_text=evidence_text.rsplit('\n\n',1)[1]
            if '</untrusted_tool_result>' in evidence_text:
                evidence_text=evidence_text.split('</untrusted_tool_result>',1)[0].strip()
            evidence=json.loads(evidence_text)
            while isinstance(evidence,dict) and isinstance(evidence.get('result'),str):
                evidence=json.loads(evidence['result'])
            if evidence.get('status')!='SUCCEEDED' or len(evidence.get('sources',[]))<2:
                raise AssertionError({'multiple_api_candidates_missing':evidence})
            pages=evidence.get('page_reads',[])
            selected=next((row for row in pages if row.get('evidence_type')=='STATIC_PAGE' and 'milk' in row.get('excerpt','').lower() and 'rice' in row.get('excerpt','').lower() and '20 minutes' in row.get('excerpt','').lower()),None)
            if not selected or selected.get('final_url')!='https://recipes.synthetic.example/quick-milk-rice':
                raise AssertionError({'no_page_field_supported_requested_constraints':evidence})
            cook_time=re.search(r'\b\d+\s+minutes\b',selected['excerpt'],re.IGNORECASE)
            if not cook_time:
                raise AssertionError({'page_does_not_state_requested_cook_time':selected})
            kind, reply='recipe_web_compose_answer', (f"Grocy shows milk and rice in the household pantry. The page lists both and states {cook_time.group(0)}, so it fits your under-30-minute request: [{selected['title']}]({selected['final_url']}). This is a recipe suggestion based on the current pantry read; I did not change stock or the shopping list. Source evidence: static-page evidence retrieved {selected['retrieved_at_utc']}.")
        elif authoring_step and tool_result:
            kind='authoring_'+authoring_step
            tool_result_text=str(payload['messages'][-1].get('content',''))
            if '"error"' in tool_result_text:
                reply='I could not complete that recipe action; the canonical Grocy tool reported an error and made no success claim.'
            else:
                reply={
                'create':'I added HADES Synthetic Authoring Soup with milk and eggs.',
                'remove':'I removed the eggs from the recipe.',
                'restore':'I restored eggs to the recipe.',
                'fulfillment':'I checked Grocy against current stock. '+tool_result_text,
                'shopping':tool_result_text,
                }[authoring_step]
        elif authoring_step:
            kind='authoring_'+authoring_step
            if authoring_step=='household_attempt':
                owner_tools=('recipe_url_ingest','recipe-url-ingest','grocy_recipe_authoring',
                    'recipe_create_tool',
                    'grocy-recipe-authoring','recipe_create_by_name_tool','recipe_update_tool',
                    'recipe_add_ingredient_tool','recipe_remove_ingredient_tool')
                exposed=[row.get('function',{}).get('name','') for row in payload.get('tools',[])
                    if isinstance(row,dict) and any(marker in row.get('function',{}).get('name','').lower() for marker in owner_tools)]
                if exposed:
                    raise AssertionError('household model catalog exposed owner recipe tools: '+repr(exposed))
                reply="Only the owner can create or change saved recipes. I didn't change anything."
                call=None
                household_owner_tools_exposed=exposed
                # The normal response path below emits a deterministic synthetic
                # denial; no tool call or canonical Grocy request is made.
                kind='authoring_household_attempt'
            else:
                suffix={
                    'create':'recipe_create_by_name_tool',
                    'remove':'recipe_remove_ingredient_tool',
                    'restore':'recipe_add_ingredient_tool',
                    'fulfillment':'recipe_fulfillment_tool',
                    'shopping':'recipe_add_to_shopping_tool',
                }[authoring_step]
                args={
                    'create':{'name':'HADES Synthetic Authoring Soup','description':'Synthetic authenticated UI acceptance fixture.','ingredients':'[{"product":"milk","amount":1},{"product":"eggs","amount":2}]'},
                    'remove':{'position_id':101},
                    'restore':{'recipe':'HADES Synthetic Authoring Soup','product':'eggs','amount':2},
                    'fulfillment':{'recipe':'HADES Synthetic Authoring Soup'},
                    'shopping':{'recipe':'HADES Synthetic Authoring Soup'},
                }[authoring_step]
                tool_name=next((row.get('function',{}).get('name','') for row in payload.get('tools',[]) if isinstance(row,dict) and row.get('function',{}).get('name','').endswith(suffix)), '')
                if not tool_name:
                    kind, reply='authoring_tool_unavailable', 'That recipe action is not available in this session.'
                    call=None
                else:
                    call={'id':'call-synthetic-'+authoring_step,'type':'function','function':{'name':tool_name,'arguments':json.dumps(args)}}
                    reply=''
        elif scope_turn and 'tool_search' in [row.get('function',{}).get('name') for row in payload.get('tools',[]) if isinstance(row,dict)] and not prior_search:
            kind, reply='recipe_scope_probe_search', ''
        elif scope_turn and prior_search and not prior_raw_attempt:
            kind, reply='recipe_scope_raw_call_probe', ''
        elif scope_turn: kind, reply='recipe_scope_probe', 'No canonical change was made.'
        else: kind, reply='unexpected_user_inference', 'UNEXPECTED_MODEL_INVOCATION'
        record={'kind':kind}
        if kind.startswith('authoring_') or kind.startswith('recipe_web_compose'):
            record['available_tools']=[row.get('function',{}).get('name','') for row in payload.get('tools',[]) if isinstance(row,dict)]
            record['tool_result']=str(payload['messages'][-1].get('content',''))[:1000] if tool_result else ''
            record['current_user']=current_user[:300]
        if household_owner_tools_exposed is not None:
            record['owner_tools_exposed']=household_owner_tools_exposed
        if kind in {'post_mutation_correction','post_mutation_correction_context_probe'}:
            record['available_tools']=[row.get('function',{}).get('name','') for row in payload.get('tools',[]) if isinstance(row,dict)]
            record['current_user']=current_user
            record['prior_action_ack_visible']=any(
                'added milk to the shared shopping list and verified it.' in message.casefold()
                for message in assistant_messages
            )
        if kind=='unexpected_user_inference':
            record['current_user']=current_user[:300]
        if kind in {'recipe_scope_probe','recipe_scope_raw_call_probe'}:
            actor='household' if 'beta-scope-probe' in current_user else 'owner'
            record.update({'probe_actor':actor, 'prompt':current_user, 'tools':[row.get('function',{}).get('name','') for row in payload.get('tools',[]) if isinstance(row,dict)], 'tool_search_results':[str(row.get('content','')) for row in tool_messages]})
        with calls_lock:
            with calls_file.open('a') as out: out.write(json.dumps(record)+'\n')
        model='synthetic-no-call'; ident='synthetic-grocy-metadata'; now=int(time.time())
        call=locals().get('call')
        if kind=='recipe_scope_probe_search': call={'id':'call-synthetic-scope-search','type':'function','function':{'name':'tool_search','arguments':json.dumps({'queries':['recipe URL preview','recipe_create_by_name_tool','recipe_update_tool','recipe_set_servings'], 'limit':20})}}
        elif kind=='recipe_scope_raw_call_probe': call={'id':'call-synthetic-raw-serving','type':'function','function':{'name':'tool_call','arguments':json.dumps({'name':'mcp__grocy_recipe_authoring__recipe_set_servings','arguments':{}})}}
        if payload.get('stream'):
            chunks=[
              {'id':ident,'object':'chat.completion.chunk','created':now,'model':model,'choices':[{'index':0,'delta':({'role':'assistant','tool_calls':[{'index':0,**call}]} if call else {'role':'assistant','content':reply}),'finish_reason':None}]},
              {'id':ident,'object':'chat.completion.chunk','created':now,'model':model,'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls' if call else 'stop'}]},
            ]
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Cache-Control','no-cache'); self.end_headers()
            for chunk in chunks: self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode()); self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n'); self.wfile.flush()
        else:
            message={'role':'assistant','content':None if call else reply}
            body=json.dumps({'id':ident,'object':'chat.completion','created':now,'model':model,'choices':[{'index':0,'message':message,'finish_reason':'stop'}]}).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
port_file.write_text(str(server.server_port))
server.serve_forever()
PY
python3 "$work/model.py" "$work/model.port" "$work/model-calls.jsonl" >"$work/model.log" 2>&1 &
model_pid=$!
for _ in $(seq 1 50); do [[ -s "$work/model.port" ]] && break; kill -0 "$model_pid" 2>/dev/null || { cat "$work/model.log" >&2; exit 1; }; sleep 0.1; done
[[ -s "$work/model.port" ]] || { echo 'FAIL deterministic model responder did not bind' >&2; exit 1; }
model_url="http://127.0.0.1:$(cat "$work/model.port")/v1"

step='starting disposable Open WebUI'
docker volume create "$webui_volume" >/dev/null
docker run -d --name "$webui_name" --add-host host.docker.internal:host-gateway \
  -p "127.0.0.1:${webui_port}:8080" -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
  -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
  -v "$webui_volume:/app/backend/data" "$webui_image" >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

step='creating synthetic identities'
signup() { curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" -H 'Content-Type: application/json' --data "{\"name\":\"$1\",\"email\":\"$2\",\"password\":\"Synthetic-Only-123!\"}"; }
alpha_json=$(signup Alpha alpha-grocy@example.invalid)
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha_json")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$alpha_json")
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data '{"name":"Beta","email":"beta-grocy@example.invalid","password":"Synthetic-Only-123!","role":"user"}' >/dev/null
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data '{"name":"Gamma","email":"gamma-grocy@example.invalid","password":"Synthetic-Only-123!","role":"user"}' >/dev/null
beta_id=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/users/" -H "Authorization: Bearer $alpha_token" | python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users",x.get("items",[])); print(next(u["id"] for u in rows if u.get("email")=="beta-grocy@example.invalid"))')
gamma_id=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/users/" -H "Authorization: Bearer $alpha_token" | python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users",x.get("items",[])); print(next(u["id"] for u in rows if u.get("email")=="gamma-grocy@example.invalid"))')

step='configuring Hermes gateway'
export HERMES_HOME="$work/hermes"
mkdir -m 700 "$HERMES_HOME"
hermes profile create hades --no-alias --no-skills >/dev/null
chmod 700 "$HERMES_HOME/profiles" "$HERMES_HOME/profiles/hades"
hermes_bin=$(readlink -f "$(command -v hermes)")
hermes_python=${HADES_HERMES_PYTHON:-"$(dirname "$hermes_bin")/python3.11"}
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python interpreter unavailable; set HADES_HERMES_PYTHON when using a versioned runtime' >&2; exit 2; }
export HADES_HERMES_EXECUTABLE="$hermes_bin"
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
cat >"$work/synthetic-mcp.py" <<'PY'
import asyncio
import json
import os
import sys
from urllib.request import Request, urlopen

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

catalogs = {
    "grocy": [
        "stock_overview_tool", "shopping_list_view_tool", "recipes_list_tool",
        "recipe_details_tool", "recipe_add_to_shopping_tool",
    ],
    "grocy-recipe-authoring": [
        "recipe_create_by_name_tool", "recipe_update_tool",
        "recipe_add_ingredient_tool", "recipe_remove_ingredient_tool",
        "recipe_set_servings",
    ],
    "recipe-url-ingest": [
        "recipe_url_preview", "recipe_url_apply", "recipe_paste_preview",
    ],
    "public-research": ["public_research"],
}
name = sys.argv[1]

async def list_tools(_context, _params):
    return ListToolsResult(tools=[Tool(
        name=tool_name,
        description="Synthetic scope-acceptance tool; never accesses canonical state.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    ) for tool_name in catalogs[name]])

async def call_tool(_context, params):
    if name == "grocy" and params.name == "stock_overview_tool":
        base = os.environ['GROCY_URL'].rstrip('/')
        headers = {'GROCY-API-KEY': os.environ['GROCY_API_KEY']}
        def get(path):
            with urlopen(Request(base + path, headers=headers), timeout=5) as response:
                return json.load(response)
        products = {row['id']: row['name'] for row in get('/api/objects/products')}
        result = {"fixture": True, "authority": "synthetic-grocy-http", "stock": [
            {"name": products.get(row['product_id'], 'unknown'), "amount": row['amount_aggregated']}
            for row in get('/api/stock') if row.get('amount_aggregated', 0) > 0
        ]}
    elif name == "public-research" and params.name == "public_research":
        result = {
            "status": "SUCCEEDED", "query": params.arguments.get("query"),
            "sources": [
                {"source_id":"src-title-trap","title":"Quick Rice Recipe in 15 Minutes","url":"https://recipes.synthetic.example/quick-rice","evidence_type":"SEARCH_SNIPPET","retrieved_at_utc":"2026-09-27T11:59:00Z","excerpt":"A quick rice dinner made with broth, vegetables, and herbs."},
                {"source_id":"src-quick-milk-rice","title":"Quick Milk and Rice Pudding","url":"https://recipes.synthetic.example/quick-milk-rice","evidence_type":"SEARCH_SNIPPET","retrieved_at_utc":"2026-09-27T11:58:00Z","excerpt":"A quick pudding with rice and milk; cooking time 20 minutes."},
            ],
            "page_reads": [
                {"source_id":"page-title-trap","discovered_from_source_id":"src-title-trap","evidence_type":"STATIC_PAGE","title":"Quick Rice Recipe in 15 Minutes","url":"https://recipes.synthetic.example/quick-rice","final_url":"https://recipes.synthetic.example/quick-rice","retrieved_at_utc":"2026-09-27T12:01:00Z","excerpt":"Ingredients: rice, broth, carrots, and herbs. Cook for 15 minutes.","truncated":False},
                {"source_id":"page-quick-milk-rice","discovered_from_source_id":"src-quick-milk-rice","evidence_type":"STATIC_PAGE","title":"Quick Milk and Rice Pudding","url":"https://recipes.synthetic.example/quick-milk-rice","final_url":"https://recipes.synthetic.example/quick-milk-rice","retrieved_at_utc":"2026-09-27T12:00:00Z","excerpt":"Ingredients: 1 cup milk, 1/2 cup rice, sugar, and cinnamon. Simmer for 20 minutes.","truncated":False},
            ], "limitations": []
        }
    else:
        result = {"fixture": True, "tool": params.name}
    record_path = os.environ.get("HADES_GROCY_UI_COMPOSITION_CALLS_FILE")
    if record_path:
        with open(record_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({"server": name, "tool": params.name, "result": result}, sort_keys=True) + "\n")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

server = Server(name, on_list_tools=list_tools, on_call_tool=call_tool)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

asyncio.run(main())
PY
chmod 600 "$work/synthetic-mcp.py"
cat >"$HERMES_HOME/profiles/hades/config.yaml" <<YAML
model:
  default: synthetic-no-call
  provider: custom
  base_url: $model_url
tools:
  tool_search:
    enabled: ${HADES_GROCY_UI_TOOL_SEARCH:-off}
mcp_servers:
  grocy:
    command: $hermes_python
    args: ["$work/synthetic-mcp.py", "grocy"]
    timeout: 30
    connect_timeout: 10
  grocy-recipe-authoring:
    command: $hermes_python
    args: ["$work/synthetic-mcp.py", "grocy-recipe-authoring"]
    timeout: 30
    connect_timeout: 10
  recipe-url-ingest:
    command: $hermes_python
    args: ["$work/synthetic-mcp.py", "recipe-url-ingest"]
    timeout: 30
    connect_timeout: 10
YAML
chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
if [[ ${HADES_GROCY_UI_RECIPE_WEB_COMPOSE:-0} == 1 ]]; then
  "$hermes_python" - "$HERMES_HOME/profiles/hades/config.yaml" "$hermes_python" "$work/synthetic-mcp.py" "$grocy_url" "$work/composition-mcp.jsonl" <<'PY'
import sys, yaml
path, executable, server, grocy_url, calls_file = sys.argv[1:]
with open(path, encoding='utf-8') as stream:
    config = yaml.safe_load(stream)
config['mcp_servers']['grocy']['env'] = {
    'GROCY_URL': grocy_url,
    'GROCY_API_KEY': 'synthetic-grocy-ui-key',
    'HADES_GROCY_UI_COMPOSITION_CALLS_FILE': calls_file,
}
config['mcp_servers']['public-research'] = {
    'command': executable,
    'args': [server, 'public-research'],
    'env': {'HADES_GROCY_UI_COMPOSITION_CALLS_FILE': calls_file},
    'timeout': 30,
    'connect_timeout': 10,
}
with open(path, 'w', encoding='utf-8') as stream:
    yaml.safe_dump(config, stream, sort_keys=False)
PY
  chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
fi
if [[ ${HADES_GROCY_UI_RECIPE_AUTHORING:-0} == 1 ]]; then
  grocy_mcp=${HADES_GROCY_MCP_EXECUTABLE:-grocy-mcp}
  [[ -x "$grocy_mcp" ]] || { echo 'FAIL set HADES_GROCY_MCP_EXECUTABLE to the pinned grocy-mcp executable' >&2; exit 2; }
  "$hermes_python" - "$HERMES_HOME/profiles/hades/config.yaml" "$grocy_mcp" "$grocy_url" <<'PY'
import sys, yaml
path, executable, url = sys.argv[1:]
with open(path, encoding='utf-8') as stream:
    config = yaml.safe_load(stream)
config['mcp_servers']['grocy'] = {
    'command': executable,
    'args': ['--transport=stdio'],
    'env': {'GROCY_URL': url, 'GROCY_API_KEY': 'synthetic-grocy-ui-key'},
    'timeout': 30,
    'connect_timeout': 10,
}
with open(path, 'w', encoding='utf-8') as stream:
    yaml.safe_dump(config, stream, sort_keys=False)
PY
  chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
fi
if [[ -n ${HADES_GROCY_UI_HINDSIGHT_PLUGIN_REF:-} ]]; then
  [[ "$HADES_GROCY_UI_HINDSIGHT_PLUGIN_REF" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'FAIL HADES_GROCY_UI_HINDSIGHT_PLUGIN_REF must be an immutable 40-character commit' >&2
    exit 2
  }
  # The HADES overlay imports the provider during interpreter startup, before
  # Hermes applies the selected profile override; install it at process-home scope.
  hermes plugins install hindsight \
    --ref "$HADES_GROCY_UI_HINDSIGHT_PLUGIN_REF" --no-deps --enable >/dev/null
fi
if [[ ${HADES_GROCY_UI_GATEWAY_STANDALONE:-0} == 1 ]]; then
  # Hermes 0.21.5 requires standalone=true for this disposable single-profile
  # gateway; production multiplexing remains a separate deployment contract.
  cat >>"$HERMES_HOME/profiles/hades/config.yaml" <<'YAML'
gateway:
  standalone: true
YAML
fi
export PYTHONPATH="$hermes_overlay_dir:$repo_dir:$hermes_source"
export HADES_HERMES_WORKING_DIRECTORY=${HADES_HERMES_WORKING_DIRECTORY:-$repo_dir}
export HADES_TASK_STATE_FILE="$work/tasks.sqlite" HADES_EPSILON_STATE_FILE="$work/epsilon.sqlite" HADES_GROCY_AUDIT_FILE="$work/grocy-audit.jsonl"
export HADES_OWNER_SUBJECT_IDS="$alpha_id" GROCY_URL="$grocy_url" GROCY_API_KEY=synthetic-grocy-ui-key
export API_SERVER_ENABLED=true API_SERVER_KEY="$api_key" API_SERVER_HOST="$docker_gateway" API_SERVER_PORT="$gateway_port"
export OPENAI_API_KEY=synthetic-unused OPENAI_BASE_URL=http://127.0.0.1:9/v1 MODEL=synthetic-no-call HERMES_ACCEPT_HOOKS=1
gateway_url="http://${docker_gateway}:${gateway_port}"
hermes -p hades gateway run -v >"$work/hermes.log" 2>&1 &
gateway_pid=$!
for _ in $(seq 1 90); do curl -fsS "$gateway_url/health" >/dev/null 2>&1 && break; kill -0 "$gateway_pid" 2>/dev/null || { cat "$work/hermes.log" >&2; exit 1; }; sleep 1; done
curl -fsS "$gateway_url/health" >/dev/null
gateway_models=$(curl -fsS -H "Authorization: Bearer $api_key" "$gateway_url/v1/models")
model_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); print(x["data"][0]["id"] if x.get("data") else "")' <<<"$gateway_models")
[[ -n "$model_id" ]] || { cat "$work/hermes.log" >&2; echo 'FAIL Hermes advertised no model' >&2; exit 1; }

step='configuring per-user identity and model access'
curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${gateway_port}/v1\"],\"OPENAI_API_KEYS\":[\"${api_key}\"],\"OPENAI_API_CONFIGS\":{\"0\":{\"headers\":{\"X-Hermes-Session-Key\":\"hades-user-{{USER_ID}}\"}}}}" >/dev/null
model_access=$(python3 - "$model_id" "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import json, sys
model, *users = sys.argv[1:]
print(json.dumps({'id':model, 'name':model, 'access_grants':[{'principal_type':'user','principal_id':user,'permission':'read'} for user in users]}))
PY
)
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/models/model/access/update" -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data "$model_access" >/dev/null

step='authenticated household pantry/list acceptance'
report="$work/acceptance.json"
if [[ ${HADES_GROCY_UI_RECIPE_WEB_COMPOSE_ONLY:-0} == 1 ]]; then
  printf '{"mode":"recipe_web_compose_only"}\n' >"$report"
  chmod 600 "$report"
else
  HADES_GROCY_UI_BASE_URL="http://127.0.0.1:${webui_port}" HADES_GROCY_UI_EMAIL=beta-grocy@example.invalid \
    HADES_GROCY_UI_GAMMA_EMAIL=gamma-grocy@example.invalid \
    HADES_GROCY_UI_OWNER_EMAIL=alpha-grocy@example.invalid \
    HADES_GROCY_UI_INCLUDE_OWNER_SERVING="${HADES_GROCY_UI_INCLUDE_OWNER_SERVING:-0}" \
    HADES_GROCY_UI_RECIPE_SCOPE_PROBE="${HADES_GROCY_UI_RECIPE_SCOPE_PROBE:-0}" \
    HADES_GROCY_UI_RECIPE_SCOPE_ONLY="${HADES_GROCY_UI_RECIPE_SCOPE_ONLY:-0}" \
    HADES_GROCY_UI_RECIPE_AUTHORING="${HADES_GROCY_UI_RECIPE_AUTHORING:-0}" \
    HADES_GROCY_UI_PASSWORD='Synthetic-Only-123!' HADES_GROCY_UI_MODEL_ID="$model_id" \
    HADES_GROCY_UI_FAILURE_FILE="$work/grocy-unavailable" HADES_GROCY_UI_REPORT="$report" \
    node "$repo_dir/scripts/dom-grocy-authenticated-household.js"
fi

if [[ ${HADES_GROCY_UI_RECIPE_WEB_COMPOSE:-0} == 1 ]]; then
  step='authenticated pantry and public-research composition'
  composition_start_request_count=$(wc -l < "$work/grocy-requests.jsonl")
  HADES_GROCY_UI_BASE_URL="http://127.0.0.1:${webui_port}" \
    HADES_GROCY_UI_OWNER_EMAIL=alpha-grocy@example.invalid \
    HADES_GROCY_UI_PASSWORD='Synthetic-Only-123!' HADES_GROCY_UI_MODEL_ID="$model_id" \
    node "$repo_dir/scripts/dom-grocy-web-research-compose.js"
  python3 - "$work/composition-mcp.jsonl" "$work/model-calls.jsonl" "$work/grocy-requests.jsonl" "$composition_start_request_count" <<'PY'
import json, sys
from pathlib import Path
mcp=[json.loads(row) for row in Path(sys.argv[1]).read_text().splitlines() if row.strip()]
model=[json.loads(row) for row in Path(sys.argv[2]).read_text().splitlines() if row.strip()]
requests=[json.loads(row) for row in Path(sys.argv[3]).read_text().splitlines() if row.strip()]
composition_requests=requests[int(sys.argv[4]):]
compound=[row for row in model if row.get('kind','').startswith('recipe_web_compose')]
assert [row['kind'] for row in compound]==['recipe_web_compose_stock','recipe_web_compose_research','recipe_web_compose_answer'], compound
assert [(row['server'],row['tool']) for row in mcp]==[('grocy','stock_overview_tool'),('public-research','public_research')], mcp
assert 'milk' in json.dumps(compound[1]).lower() and 'rice' in json.dumps(compound[1]).lower(), compound
research_result=mcp[1]['result']
assert research_result['query']=='quick milk rice recipe under 30 minutes', research_result
assert len(research_result['sources'])==2 and len(research_result['page_reads'])==2, research_result
title_trap=next(row for row in research_result['page_reads'] if row['source_id']=='page-title-trap')
selected=next(row for row in research_result['page_reads'] if row['source_id']=='page-quick-milk-rice')
assert 'milk' not in title_trap['excerpt'].lower() and '20 minutes' in selected['excerpt'].lower(), research_result
assert not any(any(term in name.lower() for term in ('shopping_list_add','recipe_create','recipe_update','add_to_shopping')) for row in compound for name in row.get('available_tools',[])), compound
assert composition_requests and all(row['method']=='GET' for row in composition_requests), composition_requests
print('PASS sequential synthetic Grocy stock then public-research calls; compound tool catalog remained read-only')
PY
fi

if [[ ${HADES_GROCY_UI_RECIPE_AUTHORING:-0} == 1 ]]; then
  curl -fsS "$grocy_url/api/objects/recipes/30" -H 'GROCY-API-KEY: synthetic-grocy-ui-key' >"$work/authoring-recipe.json"
  curl -fsS "$grocy_url/api/objects/recipes_pos" -H 'GROCY-API-KEY: synthetic-grocy-ui-key' >"$work/authoring-positions.json"
  curl -fsS "$grocy_url/api/objects/shopping_list" -H 'GROCY-API-KEY: synthetic-grocy-ui-key' >"$work/authoring-shopping.json"
  python3 - "$work/authoring-recipe.json" "$work/authoring-positions.json" "$work/authoring-shopping.json" <<'PY'
import json, sys
from pathlib import Path
recipe, positions, shopping = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
assert recipe['name']=='HADES Synthetic Authoring Soup', recipe
rows=[row for row in positions if row['recipe_id']==30]
assert {(row['product_id'],row['amount']) for row in rows}=={(11,1.0),(12,2.0)}, rows
assert len([row for row in shopping if row['product_id']==12 and row['amount']==1])==1, shopping
assert not [row for row in shopping if row['product_id']==11], shopping
print('PASS canonical synthetic recipe, restored ingredients, one-unit egg shortage and shortage-only shopping state verified')
PY
fi

step='verifying authority calls, household audit and model bypass'
python3 - "$work/grocy-requests.jsonl" "$work/grocy-audit.jsonl" "$beta_id" "$work/hermes.log" "$work/model-calls.jsonl" "${HADES_GROCY_UI_INCLUDE_OWNER_SERVING:-0}" "${HADES_GROCY_UI_RECIPE_SCOPE_PROBE:-0}" "${HADES_GROCY_UI_RECIPE_SCOPE_ONLY:-0}" "${HADES_GROCY_UI_RECIPE_AUTHORING:-0}" <<'PY'
import json, sys
from pathlib import Path
requests=[json.loads(row) for row in Path(sys.argv[1]).read_text().splitlines() if row.strip()]
owner_serving=sys.argv[6]=='1'
scope_probe=sys.argv[7]=='1'
scope_only=sys.argv[8]=='1'
owner_only=__import__('os').environ.get('HADES_GROCY_UI_OWNER_SERVING_ONLY')=='1'
authoring_only=sys.argv[9]=='1'
compose_only=__import__('os').environ.get('HADES_GROCY_UI_RECIPE_WEB_COMPOSE_ONLY')=='1'
if compose_only:
    assert requests and all(row['method']=='GET' for row in requests), requests
    assert not Path(sys.argv[2]).read_text().strip(), Path(sys.argv[2]).read_text()
    logs=Path(sys.argv[4]).read_text(errors='replace')
    assert 'API recipe/web compound turn narrowed to' in logs
    assert 'API homelab intent narrowed' not in logs
    assert 'HADES compatibility overlay initialization failed' not in logs
    calls=[json.loads(row) for row in Path(sys.argv[5]).read_text().splitlines() if row.strip()]
    kinds=[row.get('kind') for row in calls]
    assert kinds.count('recipe_web_compose_stock')==1 and kinds.count('recipe_web_compose_research')==1 and kinds.count('recipe_web_compose_answer')==1, kinds
    assert all(kind in {'title','suggestions','tags','recipe_web_compose_stock','recipe_web_compose_research','recipe_web_compose_answer'} for kind in kinds), kinds
    print('PASS authenticated recipe website search routing, API-field answer shaping, and read-only pantry access')
    sys.exit(0)
assert (not requests if scope_only else bool(requests) and all(row['keyValid'] for row in requests)), requests
serving_writes=[row for row in requests if row['method']=='PUT' and row['path']=='/api/objects/recipes/21']
assert len(serving_writes)==(1 if owner_serving else 0), serving_writes
if owner_serving: assert serving_writes[0]['body']=={'base_servings':6}, serving_writes
if scope_only:
    assert not requests, requests
    assert not Path(sys.argv[2]).read_text().strip()
    calls=[json.loads(row) for row in Path(sys.argv[5]).read_text().splitlines() if row.strip()]
    household_rows=[row for row in calls if row.get('probe_actor')=='household']
    owner_rows=[row for row in calls if row.get('probe_actor')=='owner']
    assert household_rows and owner_rows, calls
    household=max(household_rows, key=lambda row: len(row.get('tools', [])))
    owner=max(owner_rows, key=lambda row: len(row.get('tools', [])))
    household_tools=set(household['tools'])
    owner_tools=set(owner['tools'])
    privileged=('recipe_url_ingest','recipe-url-ingest','grocy_recipe_authoring','grocy-recipe-authoring',
        'recipe_create_tool','recipe_create_by_name_tool','recipe_update_tool','recipe_add_ingredient_tool','recipe_remove_ingredient_tool',
        'recipe_set_servings')
    if __import__('os').environ.get('HADES_GROCY_UI_TOOL_SEARCH') == 'on':
        def searched(rows):
            names=set()
            for row in rows:
                for raw in row.get('tool_search_results',[]):
                    try: names.update(json.loads(raw).get('tools',{}))
                    except (TypeError,ValueError): pass
            return names
        household_search=searched(household_rows)
        owner_search=searched(owner_rows)
        assert not any(marker in name.lower() for marker in privileged for name in household_search), household_rows
        assert {'mcp__recipe_url_ingest__recipe_url_preview','mcp__grocy_recipe_authoring__recipe_create_by_name_tool',
            'mcp__grocy_recipe_authoring__recipe_update_tool'} <= owner_search, owner_rows
        assert not any('recipe_set_servings' in name.lower() for name in owner_search), owner_rows
    else:
        assert not any(marker in name.lower() for marker in privileged for name in household_tools), household
        assert {'mcp__grocy__recipes_list_tool','mcp__grocy__recipe_add_to_shopping_tool'} <= household_tools, household
        assert {'mcp__recipe_url_ingest__recipe_url_preview','mcp__grocy_recipe_authoring__recipe_create_by_name_tool',
            'mcp__grocy_recipe_authoring__recipe_update_tool'} <= owner_tools, owner
    assert all(row['kind'] in {'title','suggestions','tags','recipe_scope_probe','recipe_scope_probe_search','recipe_scope_raw_call_probe'} for row in calls), calls
    if __import__('os').environ.get('HADES_GROCY_UI_TOOL_SEARCH') == 'on':
        raw_attempts=[row for row in calls if row.get('kind')=='recipe_scope_raw_call_probe']
        assert len(raw_attempts)==2, calls
        denied_rows=[max((row for row in calls if row.get('kind')=='recipe_scope_probe' and row.get('probe_actor')==actor), key=lambda row: len(row.get('tool_search_results',[]))) for actor in ('household','owner')]
        assert {row.get('probe_actor') for row in denied_rows} == {'household','owner'}, denied_rows
        assert all(any(
            ('not available in this session' in result or 'Serving changes require' in result
             or 'The tool was NOT invoked' in result) and '"fixture": true' not in result
            for result in row.get('tool_search_results',[])
        ) for row in denied_rows), denied_rows
elif owner_only:
    assert sum(row['method']=='GET' and row['path']=='/api/objects/recipes' for row in requests)==2, requests
    # Named previews resolve through the collection; the added pre-confirmation
    # canonical check plus apply/read-back account for three detail reads.
    assert sum(row['method']=='GET' and row['path']=='/api/objects/recipes/21' for row in requests)==3, requests
    assert all(
        (row['method'], row['path']) in {
            ('GET', '/api/objects/recipes'),
            ('GET', '/api/objects/recipes/21'),
            ('PUT', '/api/objects/recipes/21'),
        }
        for row in requests
    ), requests
    assert not [row for row in requests if row['method'] in {'POST','PUT','DELETE'} and row['path'].startswith('/api/objects/shopping_list')], requests
    assert not [row for row in requests if row['method']=='GET' and row['path']=='/api/stock'], requests
    assert not Path(sys.argv[2]).read_text().strip(), 'owner-only resize unexpectedly emitted household audit events'
    logs=Path(sys.argv[4]).read_text(errors='replace')
    # This focused lane contains only the recipe-serving confirmation journey;
    # the independent preemptive shopping-list offer/decline scenario runs in
    # the full household suite below, not in owner-serving-only mode.
    if not owner_only:
        assert logs.count('Preemptive Grocy offer declined without action') == 1, logs
    assert logs.count('Recipe serving turn state')==6, logs
    assert logs.count('Recipe serving confirmation route completed without model invocation')==6, logs
    calls=[json.loads(row) for row in Path(sys.argv[5]).read_text().splitlines() if row.strip()]
    if scope_probe:
        household_rows = [row for row in calls if row.get('probe_actor') == 'household']
        owner_rows = [row for row in calls if row.get('probe_actor') == 'owner']
        assert household_rows and owner_rows, calls
        household = max(household_rows, key=lambda row: len(row.get('tools', [])))
        owner = max(owner_rows, key=lambda row: len(row.get('tools', [])))
        household_tools=set(household['tools'])
        owner_tools=set(owner['tools'])
        privileged = ('recipe_url_ingest', 'recipe-url-ingest', 'grocy_recipe_authoring',
            'grocy-recipe-authoring', 'recipe_create_tool','recipe_create_by_name_tool','recipe_update_tool',
            'recipe_add_ingredient_tool', 'recipe_remove_ingredient_tool')
        assert not any(marker in name.lower() for marker in privileged for name in household_tools), household
        assert 'mcp__grocy__recipes_list_tool' in household_tools, household
        assert 'mcp__grocy__recipe_add_to_shopping_tool' in household_tools, household
        assert 'mcp__recipe_url_ingest__recipe_url_preview' in owner_tools, owner
        assert 'mcp__grocy_recipe_authoring__recipe_create_by_name_tool' in owner_tools, owner
        assert 'mcp__grocy_recipe_authoring__recipe_update_tool' in owner_tools, owner
        if scope_only:
            assert not requests, requests
            assert not Path(sys.argv[2]).read_text().strip(), 'scope probe emitted Grocy audit events'
    assert all(row['kind'] in {'title','suggestions','tags','recipe_scope_probe'} for row in calls), calls
elif authoring_only:
    created=[row for row in requests if row['method']=='POST' and row['path']=='/api/objects/recipes' and row.get('body',{}).get('name')=='HADES Synthetic Authoring Soup']
    assert len(created)==1, created
    ingredient_creates=[row for row in requests if row['method']=='POST' and row['path']=='/api/objects/recipes_pos']
    assert len(ingredient_creates)==3, ingredient_creates
    ingredient_removes=[row for row in requests if row['method']=='DELETE' and row['path'].startswith('/api/objects/recipes_pos/')]
    assert len(ingredient_removes)==1, ingredient_removes
    assert any(row['method']=='GET' and row['path']=='/api/objects/recipes_pos' for row in requests), requests
    assert any(row['method']=='GET' and row['path']=='/api/stock' for row in requests), requests
    assert sum(row['method']=='POST' and row['path']=='/api/objects/shopping_list' for row in requests)==1, requests
    assert sum(row['method']=='GET' and row['path']=='/api/objects/shopping_list' for row in requests)>=2, requests
    authoring_calls=[json.loads(row) for row in Path(sys.argv[5]).read_text().splitlines() if row.strip()]
    expected_tools={
        'authoring_create':'recipe_create_by_name_tool',
        'authoring_remove':'recipe_remove_ingredient_tool',
        'authoring_restore':'recipe_add_ingredient_tool',
    }
    for kind, suffix in expected_tools.items():
        results=[row for row in authoring_calls if row.get('kind')==kind and row.get('tool_result')]
        assert results and any(any(name.endswith(suffix) for name in row.get('available_tools', [])) for row in results), (kind, suffix, authoring_calls)
        assert all('"error"' not in row['tool_result'] for row in results), (kind, results)
    household_attempts=[row for row in authoring_calls if row.get('kind')=='authoring_household_attempt']
    assert household_attempts and all(row.get('owner_tools_exposed')==[] for row in household_attempts), household_attempts
    complete_household_catalog=[row for row in household_attempts if 'mcp__grocy__recipes_list_tool' in row.get('available_tools', [])]
    assert complete_household_catalog, household_attempts
    owner_markers=('recipe_url_ingest','recipe-url-ingest','grocy_recipe_authoring','grocy-recipe-authoring',
        'recipe_create_tool','recipe_create_by_name_tool','recipe_update_tool','recipe_add_ingredient_tool',
        'recipe_remove_ingredient_tool')
    assert all(not any(marker in name.lower() for marker in owner_markers)
        for row in complete_household_catalog for name in row.get('available_tools', [])), complete_household_catalog
    assert not [row for row in requests if row.get('body',{}).get('name')=='Beta Unauthorized Soup'], requests
else:
    assert any(row['method']=='GET' and row['path']=='/api/stock' for row in requests), requests
    recipe_reads=sum(row['method']=='GET' and row['path']=='/api/objects/recipes' for row in requests)
    assert (18 if owner_serving else 16) <= recipe_reads <= (20 if owner_serving else 18), ('recipe read count outside bounded journey', recipe_reads)
    positions_reads=sum(row['method']=='GET' and row['path']=='/api/objects/recipes_pos' for row in requests)
    assert 15 <= positions_reads <= 17, ('recipe-position read count outside bounded journey', positions_reads)
    conversions=[row for row in requests if row['method']=='GET' and row['path'].startswith('/api/objects/quantity_unit_conversions_resolved?')]
    conversion_paths=[row['path'] for row in conversions]
    # The 2026-10-07 paired 0.11.1/0.11.4 UI replay produced identical
    # 13-read traces. Require both journey products, and cap duplicate reads;
    # the former 21-read floor encoded an older redundant request pattern.
    assert (2 <= len(conversions) <= 15
            and all('query%5B%5D=product_id%3D' in path for path in conversion_paths)
            and {path.rsplit('product_id%3D', 1)[-1] for path in conversion_paths} == {'14', '15'}), (
        'unit-conversion reads must cover both journey products without a duplicate-read storm',
        len(conversions), conversion_paths)
    writes=[row for row in requests if row['method']=='POST' and row['path']=='/api/objects/shopping_list']
    assert len(writes)==3, writes
    assert sum(row['method']=='GET' and row['path']=='/api/objects/shopping_list' for row in requests)>=(21 if owner_serving else 19), requests
    assert {row['body']['product_id'] for row in writes}=={11,12,15}, writes
    assert all(row['body']['amount']==1 for row in writes)
    assert next(row for row in writes if row['body']['product_id']==15)['body']['qu_id']==3, writes
    audit=[json.loads(row) for row in Path(sys.argv[2]).read_text().splitlines() if row.strip()]
    assert len(audit)==12 and all(row['actor_subject']==sys.argv[3] and row['scope']=='household' for row in audit), audit
    logs=Path(sys.argv[4]).read_text(errors='replace')
    assert logs.count('Household direct Grocy read completed without model invocation') >= (7 if owner_serving else 5), 'expected authenticated canonical reads plus one honest failure response'
    assert logs.count('Direct Grocy shopping-list mutation completed with read-back') == 1, 'expected one separate explicit product add'
    assert logs.count('Direct Grocy recipe add flow completed') == 6, 'expected explicit pancake and converted rice adds/retries, unsafe-unit refusal, and ambiguity clarification; the offer confirmation has its own route'
    assert logs.count('Direct Grocy recipe fulfillment completed from current turn') == 6, 'expected the accepted offer preview, exact and ingredient-matched make-again handling, canonical feasibility, natural meal planning, and pantry-first meal answers'
    assert 'Skipping HADES capability routing for Hermes auxiliary generation' in logs, 'Hermes metadata requests were not isolated from HADES actions'
    assert 'HADES compatibility overlay initialization failed' not in logs
    calls=[json.loads(row) for row in Path(sys.argv[5]).read_text().splitlines() if row.strip()]
    assert sum(row['kind']=='post_mutation_correction' for row in calls)==1, calls
    correction_call=next(row for row in calls if row['kind']=='post_mutation_correction')
    assert correction_call['prior_action_ack_visible'] is True, correction_call
    assert all(row['kind'] in {'post_mutation_correction','post_mutation_correction_context_probe'}
               for row in calls if row['kind'].startswith('post_mutation_correction')), calls
    assert not any(
        marker in name.lower()
        for marker in ('recipe_create_tool','recipe_create_by_name_tool','recipe_update_tool','recipe_add_ingredient_tool','recipe_remove_ingredient_tool')
        for name in correction_call['available_tools']
    ), correction_call
    correction_calls=[row for row in calls if row['kind'].startswith('post_mutation_correction')]
    assert all(not any(
        marker in name.lower()
        for marker in ('recipe_create_tool','recipe_create_by_name_tool','recipe_update_tool','recipe_add_ingredient_tool','recipe_remove_ingredient_tool')
        for name in row['available_tools']
    ) for row in correction_calls), correction_calls
    assert all(row['kind'] in {'title','suggestions','tags','post_mutation_correction',
                               'post_mutation_correction_context_probe','recipe_web_compose_stock',
                               'recipe_web_compose_research','recipe_web_compose_answer'} for row in calls), calls
PY
if [[ ${HADES_GROCY_UI_RECIPE_SCOPE_ONLY:-0} == 1 ]]; then
  echo 'PASS authenticated Beta/Alpha raw Hermes tool-schema scope; no Grocy calls or writes'
fi
install -m 600 "$report" "${HADES_GROCY_UI_REPORT:-/tmp/hades-grocy-household-ui-$$.json}"
if [[ ${HADES_GROCY_UI_INCLUDE_OWNER_SERVING:-0} == 1 ]]; then
  servings=$(curl -fsS "$grocy_url/api/objects/recipes/21" -H 'GROCY-API-KEY: synthetic-grocy-ui-key' | python3 -c 'import json,sys; print(json.load(sys.stdin)["base_servings"])')
  [[ "$servings" == 6 ]] || { echo "FAIL canonical serving state is $servings, expected 6" >&2; exit 1; }
  echo 'PASS owner authenticated serving preview, cross-chat isolation, household denial, same-chat confirmation/cancellation, single canonical write and read-back'
else
  if [[ ${HADES_GROCY_UI_RECIPE_SCOPE_ONLY:-0} == 1 ]]; then
    echo 'PASS authenticated Open WebUI owner-versus-household recipe tool catalog boundary'
  elif [[ ${HADES_GROCY_UI_RECIPE_WEB_COMPOSE_ONLY:-0} == 1 ]]; then
    echo 'PASS focused authenticated public-recipe composition; broad household workflows were not rerun'
  else
    echo 'PASS authenticated household pantry, expiry-aware meal suggestions, recipe feasibility and shortage adds, refusal, retry idempotency, canonical read-back, and actor audit'
    [[ ${HADES_GROCY_UI_RECIPE_SCOPE_PROBE:-0} != 1 ]] || echo 'PASS authenticated Open WebUI owner-versus-household recipe tool catalog boundary'
  fi
fi
