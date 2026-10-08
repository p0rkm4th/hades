#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_source=/mnt/shared/hades-core-usability-reset/Hermes-v0.21.5-hades-candidate
hermes_python=${HADES_WORKSPACE_TEST_HERMES_PYTHON:-$hermes_source/.venv/bin/python}
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes 0.21.5 candidate Python is unavailable' >&2; exit 2; }
[[ -d "$hermes_source" ]] || { echo 'FAIL Hermes 0.21.5 candidate source is unavailable' >&2; exit 2; }
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-workspace-escalation.XXXXXX")
chmod 700 "$work"
cleanup() {
  python3 - "$work" <<'PY'
from pathlib import Path
import shutil,sys
p=Path(sys.argv[1])
if p.name.startswith("hades-workspace-escalation.") and p.is_dir(): shutil.rmtree(p)
PY
}
trap cleanup EXIT

mkdir -m 700 "$work/home" "$work/hermes"
mkdir -m 700 "$work/hermes/plugins"
mkdir -m 700 "$work/overlay"
cp "$repo_dir/hermes/sitecustomize.py" "$work/overlay/sitecustomize.py"
cp "$repo_dir/hermes/workspace.py" "$work/overlay/workspace.py"
cp -a /mnt/shared/hades-core-usability-reset/HADES_HOME/plugins/hindsight "$work/hermes/plugins/hindsight"
HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$work/overlay:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner,synthetic-owner-two \
HADES_WORKSPACE_ENABLED=true \
HADES_WORKSPACE_ROOT="$work/hermes/workspaces" \
HERMES_DOCKER_BINARY="$(command -v docker)" \
HADES_HERMES_SANDBOX_IMAGE=docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d \
"$hermes_python" - "$repo_dir" "$work" <<'PY'
import os,re,sys
from pathlib import Path
import run_agent
import sitecustomize as hades
import workspace as workspace_policy
from tools.file_tools import read_file_tool
from tools.terminal_scope import get_terminal_scope, terminal_env

workspace_cases=(
  "Why is this Python test failing?",
  "Explain this function.",
  "Can you read the config and tell me what it does?",
  "I have a test tomorrow. Can you explain photosynthesis?",
  "That test result was weird, why?",
  "Tell me about workspace design patterns.",
)

repo,work=Path(sys.argv[1]),Path(sys.argv[2])
assert run_agent.AIAgent.run_conversation.__name__ == '_hades_run_conversation'
assert workspace_policy.is_workspace_request(workspace_cases[0])
assert workspace_policy.is_workspace_request(workspace_cases[1])
assert workspace_policy.is_workspace_request(workspace_cases[2])
assert not workspace_policy.is_workspace_request(workspace_cases[3])
assert not workspace_policy.is_workspace_request(workspace_cases[4])
assert not workspace_policy.is_workspace_request(workspace_cases[5])
assert not workspace_policy.sandbox_runtime_available(), 'test host should not qualify as rootless'
os.environ['HADES_WORKSPACE_ENABLED']='false'
assert not workspace_policy.is_workspace_request('Explain this traceback first.')
assert not workspace_policy.is_workspace_request('Why is this Python test failing?')
assert workspace_policy.is_workspace_request('Fix it.', [{'role':'user','content':'Why is this Python test failing?'}])
assert workspace_policy.is_workspace_request('Read README.md and explain how to run it.')
os.environ['HADES_WORKSPACE_ENABLED']='true'
# Exercise HADES/Hermes workspace wiring with the available rootful test engine;
# the production runtime gate remains the unmocked rootless check above.
home=Path(__import__('os').environ['HERMES_HOME'])
workspace=Path(__import__('os').environ['HERMES_HOME'])/'workspaces'/'synthetic-owner'; workspace.mkdir(parents=True,mode=0o700)
(workspace/'answer.txt').write_text('ORCHID-9472\n')
workspace_two=Path(__import__('os').environ['HERMES_HOME'])/'workspaces'/'synthetic-owner-two'; workspace_two.mkdir(parents=True,mode=0o700)
(workspace_two/'answer.txt').write_text('VIOLET-6138\n')
(work/'outside.txt').write_text('HOST-SECRET-58')

def create_agent(subject, chat):
 return run_agent.AIAgent(
  gateway_session_key=f'hades-user-{subject}', session_id=chat,
  stream_delta_callback=lambda _chunk: None, base_url='http://127.0.0.1:9/v1',
  api_key='synthetic-only', provider='custom', api_mode='chat_completions',
  model='synthetic-deep-model', enabled_toolsets=[], disabled_toolsets=[],
  quiet_mode=True, skip_context_files=True, skip_memory=True,
  skip_background_review=True, load_soul_identity=False,
 )

agent=create_agent('synthetic-owner','synthetic-unqualified-chat')
hades._hades_original_run_conversation=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('model invoked without rootless sandbox'))
runtime_denied=agent.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-unqualified-chat')
assert 'rootless sandbox' in runtime_denied.get('final_response','').lower(),runtime_denied
assert runtime_denied.get('api_calls') == 0,runtime_denied
print('PASS HADES denies workspace activation when only rootful Docker is available')
workspace_policy.sandbox_runtime_available=lambda: True
agent=create_agent('synthetic-owner','synthetic-work-chat')
calls=[]
def native_read(agent,user_message,*args,**kwargs):
 names={t['function']['name'] for t in agent.tools}
 assert names == {'read_file','search_files','write_file','patch','terminal'}, names
 assert terminal_env('TERMINAL_ENV') == 'docker'
 assert terminal_env('TERMINAL_DOCKER_NETWORK') == 'false'
 assert terminal_env('TERMINAL_DOCKER_FORWARD_ENV') == '[]'
 assert terminal_env('TERMINAL_DOCKER_IMAGE').endswith('sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d')
 assert get_terminal_scope() is not None
 raw=read_file_tool('/workspace/answer.txt',task_id=kwargs['task_id'])
 calls.append(raw)
 token=re.search(r'(?:ORCHID-9472|VIOLET-6138)',raw).group(0)
 return {'final_response':f'The token is {token}.','messages':[
  {'role':'tool','name':'read_file','content':raw},
  {'role':'assistant','content':f'The token is {token}.'}], 'api_calls':1,'completed':True}

hades._hades_original_run_conversation=native_read
answer=agent.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-work-chat')
assert 'ORCHID-9472' in answer.get('final_response',''),answer
assert calls and 'ORCHID-9472' in calls[0]
assert 'HOST-SECRET-58' not in calls[0]
assert get_terminal_scope() is None, get_terminal_scope()
print('PASS HADES exposes only the five native file/shell tools for an authenticated owner workspace turn')
print('PASS HADES binds Hermes Docker cwd to the owner workspace and disables network/env forwarding')

def fabricated_answer(agent,user_message,*args,**kwargs):
 assert {t['function']['name'] for t in agent.tools} == {'read_file','search_files','write_file','patch','terminal'}
 return {'final_response':'I read it; the token is MADE-UP-001.','messages':[
  {'role':'assistant','content':'I read it; the token is MADE-UP-001.'}], 'api_calls':1,'completed':True}

hades._hades_original_run_conversation=fabricated_answer
guarded=agent.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-work-chat')
assert 'couldn\'t verify a workspace tool result' in guarded.get('final_response','').lower(),guarded
assert 'MADE-UP-001' not in guarded.get('final_response',''),guarded
print('PASS HADES suppresses a fabricated workspace result when Hermes returns no tool response')

def ordinary_chat(agent,user_message,*args,**kwargs):
 assert agent.tools == [],agent.tools
 assert get_terminal_scope() is None,get_terminal_scope()
 return {'final_response':'Hey, good to hear from you.','messages':[{'role':'assistant','content':'Hey, good to hear from you.'}], 'api_calls':1,'completed':True}

hades._hades_original_run_conversation=ordinary_chat
ordinary=agent.run_conversation("Hey, how's it going?",task_id='synthetic-work-chat')
assert 'good to hear' in ordinary.get('final_response',''),ordinary
print('PASS a follow-on ordinary turn restores the empty tool catalog and no sandbox scope')

os.environ['HADES_WORKSPACE_ENABLED']='false'
def ask_for_traceback(agent,user_message,*args,**kwargs):
 assert agent.tools == [],agent.tools
 assert get_terminal_scope() is None,get_terminal_scope()
 return {'final_response':'Paste the traceback and I can explain it.','messages':[{'role':'assistant','content':'Paste the traceback and I can explain it.'}], 'api_calls':1,'completed':True}
hades._hades_original_run_conversation=ask_for_traceback
natural=agent.run_conversation('Explain this traceback first.',task_id='synthetic-work-chat')
assert 'paste the traceback' in natural.get('final_response','').lower(),natural
hades._hades_original_run_conversation=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('model invoked for a code-action continuation without a workspace'))
action=agent.run_conversation(
 'Fix it.',
 conversation_history=[{'role':'user','content':'Why is this Python test failing?'}],
 task_id='synthetic-work-chat',
)
assert 'workspace actions aren\'t enabled' in action.get('final_response','').lower(),action
assert action.get('api_calls') == 0,action
os.environ['HADES_WORKSPACE_ENABLED']='true'
print('PASS a traceback question stays model-first while a follow-on code action remains safely gated')

hades._hades_original_run_conversation=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('model invoked for unauthorized household workspace'))
household=create_agent('synthetic-household','synthetic-house-chat')
denied=household.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-house-chat')
assert 'not available for this account' in denied.get('final_response','').lower(),denied
assert denied.get('api_calls') == 0,denied
print('PASS household subject receives no owner workspace tool or model invocation')

hades._hades_original_run_conversation=native_read
second_owner=create_agent('synthetic-owner-two','synthetic-second-owner-chat')
second=second_owner.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-second-owner-chat')
assert 'VIOLET-6138' in second.get('final_response',''),second
assert 'ORCHID-9472' not in second.get('final_response',''),second
assert calls and 'VIOLET-6138' in calls[-1] and 'ORCHID-9472' not in calls[-1],calls[-1]
print('PASS authenticated subjects receive distinct per-subject workspace mounts')
PY
