#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
stage_root=${HADES_STAGE_ROOT:-/opt/hades-stage}
export HADES_STAGE_ROOT="$stage_root"
hermes_source=${HADES_WORKSPACE_TEST_HERMES_SOURCE:-$stage_root/Hermes-v0.21.5-hades-candidate}
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
cp -a "$stage_root/HADES_HOME/plugins/hindsight" "$work/hermes/plugins/hindsight"
HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$work/overlay:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner,synthetic-owner-two \
HADES_WORKSPACE_ENABLED=true \
HADES_WORKSPACE_ROOT="$work/hermes/workspaces" \
HERMES_DOCKER_BINARY="${HADES_WORKSPACE_DOCKER_BINARY:-$(command -v docker)}" \
HADES_HERMES_SANDBOX_IMAGE="${HADES_WORKSPACE_TEST_SANDBOX_IMAGE:-docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d}" \
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
patch_result={'role':'tool','name':'patch','content':'{"files_modified":["/workspace/geometry.py"]}'}
test_call={'role':'assistant','tool_calls':[{'id':'test-1','type':'function','function':{'name':'terminal','arguments':'{"command":"python -m unittest"}'}}]}
passing_test={'role':'tool','name':'terminal','tool_call_id':'test-1','content':'{"exit_code":0,"output":"Ran 2 tests in 0.01s\\n\\nOK"}'}
assert workspace_policy.has_successful_workspace_code_mutation([patch_result])
assert workspace_policy.workspace_code_verification_notice([patch_result])
assert workspace_policy.workspace_code_verification_notice([patch_result,test_call,passing_test]) is None
assert 'did not pass' in workspace_policy.workspace_code_verification_notice([
 patch_result,test_call,{'role':'tool','name':'terminal','tool_call_id':'test-1','content':'{"exit_code":1,"output":"FAILED"}'},
]).lower()
test_call_two={'role':'assistant','tool_calls':[{'id':'test-2','type':'function','function':{'name':'terminal','arguments':'{"command":"python -m unittest"}'}}]}
failed_test={'role':'tool','name':'terminal','tool_call_id':'test-1','content':'{"exit_code":1,"output":"FAILED"}'}
passing_test_two={'role':'tool','name':'terminal','tool_call_id':'test-2','content':'{"exit_code":0,"output":"Ran 2 tests in 0.01s\\n\\nOK"}'}
assert workspace_policy.workspace_code_verification_notice([
 patch_result,test_call,failed_test,test_call_two,passing_test_two,
]) is None
assert 'did not pass' in workspace_policy.workspace_code_verification_notice([
 patch_result,test_call_two,passing_test_two,test_call,failed_test,
]).lower()
assert workspace_policy.workspace_code_verification_notice([
 patch_result,test_call,passing_test,test_call_two,
])
prior_user={'role':'user','content':'Fix the previous geometry test.'}
prior_test_history=[prior_user,test_call,passing_test]
current_user={'role':'user','content':'Fix a different current failure.'}
current_patch_result={'role':'tool','name':'patch','content':'{"files_modified":["/workspace/current.py"]}'}
stale_test_transcript=prior_test_history+[current_user,current_patch_result]
current_turn_result={
 'messages':stale_test_transcript,'current_turn_user_idx':3,
 'turn_id':'turn-current',
}
current_turn=workspace_policy.current_workspace_turn_messages(
 current_turn_result,expected_turn_id='turn-current',
 expected_user_message=current_user['content'],
)
assert current_turn == [current_user,current_patch_result],current_turn
assert workspace_policy.workspace_code_test_status(current_turn) == 'unverified'
assert workspace_policy.workspace_code_verification_notice(current_turn)
stale_tool_transcript=prior_test_history+[current_user]
assert not workspace_policy.has_workspace_tool_result(
 workspace_policy.current_workspace_turn_messages({
  'messages':stale_tool_transcript,'current_turn_user_idx':3,'turn_id':'turn-current',
 },expected_turn_id='turn-current',expected_user_message=current_user['content'])
)
assert workspace_policy.current_workspace_turn_messages({
 'messages':stale_test_transcript,
},expected_turn_id='turn-current',expected_user_message=current_user['content']) == []
assert workspace_policy.current_workspace_turn_messages({
 'messages':stale_test_transcript,'current_turn_user_idx':True,'turn_id':'turn-current',
},expected_turn_id='turn-current',expected_user_message=current_user['content']) == []
assert workspace_policy.current_workspace_turn_messages({
 'messages':stale_test_transcript,'current_turn_user_idx':0,'turn_id':'turn-current',
},expected_turn_id='turn-current',expected_user_message=current_user['content']) == []
assert workspace_policy.current_workspace_turn_messages({
 'messages':stale_test_transcript,'current_turn_user_idx':3,'turn_id':'stale-turn',
},expected_turn_id='turn-current',expected_user_message=current_user['content']) == []
assert workspace_policy.current_workspace_turn_messages({
 'messages':stale_test_transcript,'current_turn_user_idx':3,'turn_id':'turn-current',
},expected_turn_id='turn-current',expected_user_message='A different active request.') == []
fresh_test_transcript=prior_test_history+[
 current_user,current_patch_result,test_call_two,passing_test_two,
]
assert workspace_policy.workspace_code_verification_notice(
 workspace_policy.current_workspace_turn_messages({
  'messages':fresh_test_transcript,'current_turn_user_idx':3,'turn_id':'turn-current',
 },expected_turn_id='turn-current',expected_user_message=current_user['content'])
) is None
unrelated_call={'role':'assistant','tool_calls':[{'id':'pwd-1','type':'function','function':{'name':'terminal','arguments':'{"command":"pwd"}'}}]}
assert workspace_policy.workspace_code_verification_notice([patch_result,unrelated_call,
 {'role':'tool','name':'terminal','tool_call_id':'pwd-1','content':'{"exit_code":0,"output":"/workspace"}'}])
assert workspace_policy.workspace_code_verification_notice([
 {'role':'tool','name':'write_file','content':'{"files_modified":["/workspace/README.md"]}'}
]) is None
real_rootless=os.environ.get('HADES_WORKSPACE_TEST_REAL_ROOTLESS','false').strip().lower() == 'true'
assert run_agent.AIAgent.run_conversation.__name__ == '_hades_run_conversation'
assert workspace_policy.is_workspace_request(workspace_cases[0])
assert workspace_policy.is_workspace_request(workspace_cases[1])
assert workspace_policy.is_workspace_follow_up_text('continue')
assert workspace_policy.is_workspace_follow_up_text('do that instead')
assert not workspace_policy.is_workspace_follow_up_text('Explain generators')
from types import SimpleNamespace
from gateway.run_turn import GatewayTurnMixin
assert hades._hades_install_gateway_route_patch()
gateway_fast_url=os.environ.get('HADES_FAST_COMPLETION_BASE_URL')
os.environ['HADES_FAST_COMPLETION_BASE_URL']='http://127.0.0.1:11437/v1'
gateway_route=GatewayTurnMixin._resolve_turn_agent_config(
 SimpleNamespace(_service_tier=None),'continue','qwen3.6:35b',{
  'provider':'custom','requested_provider':'custom',
  'base_url':'http://127.0.0.1:11434/v1','api_mode':'chat_completions',
  'command':None,'args':[],'capabilities':{},
 },
)
if gateway_fast_url is None:
 os.environ.pop('HADES_FAST_COMPLETION_BASE_URL',None)
else:
 os.environ['HADES_FAST_COMPLETION_BASE_URL']=gateway_fast_url
assert gateway_route['model']=='qwen3.6:35b',gateway_route
assert gateway_route['runtime']['base_url']=='http://127.0.0.1:11434/v1',gateway_route
print('PASS gateway keeps a context-dependent continuation on the action-capable model')
assert workspace_policy.is_workspace_request(workspace_cases[2])
assert not workspace_policy.is_workspace_request(workspace_cases[3])
assert not workspace_policy.is_workspace_request(workspace_cases[4])
assert not workspace_policy.is_workspace_request(workspace_cases[5])
if real_rootless:
 assert workspace_policy.sandbox_runtime_available(), 'configured test daemon must report rootless'
 assert workspace_policy.pinned_image_available(), 'pinned sandbox image must be present in test daemon'
 print('PASS isolated test daemon reports rootless and has the exact pinned sandbox image')
else:
 assert not workspace_policy.sandbox_runtime_available(), 'test host should not qualify as rootless'
os.environ['HADES_WORKSPACE_ENABLED']='false'
assert not workspace_policy.is_workspace_request('Explain this traceback first.')
assert not workspace_policy.is_workspace_request('Why is this Python test failing?')
assert workspace_policy.is_workspace_request('Fix it.', [{'role':'user','content':'Why is this Python test failing?'}])
assert workspace_policy.is_workspace_request('Read README.md and explain how to run it.')
assert not workspace_policy.is_workspace_request('Find where this project configures request timeouts.')
os.environ['HADES_WORKSPACE_ENABLED']='true'
assert workspace_policy.is_workspace_read_only_request('Why is this Python test failing?')
assert workspace_policy.is_workspace_read_only_request('Explain this function.')
assert workspace_policy.is_workspace_read_only_request('Find where this project configures request timeouts.')
assert not workspace_policy.is_workspace_read_only_request(
 'Run a shell command in the workspace and tell me the exact token from answer.txt.'
)
assert not hades._hades_should_use_direct_web_search(
 'Find where this project configures request timeouts.', True)
assert hades._hades_should_use_direct_web_search(
 'Search the web for current request-timeout guidance.', True)
assert workspace_policy.is_workspace_diagnosis_request('Why is this Python test failing?')
assert not workspace_policy.is_workspace_diagnosis_request('Read answer.txt and tell me the exact token.')
assert not workspace_policy.is_workspace_read_only_request('Fix it.')
workspace_search_schema=next(t['function']['parameters'] for t in workspace_policy.get_workspace_tools(read_only=True)
 if t['function']['name']=='search_files')
assert 'target' in workspace_search_schema['required'],workspace_search_schema
assert workspace_search_schema['properties']['target']['description'].startswith('Required.'),workspace_search_schema
assert {t['function']['name'] for t in workspace_policy.get_workspace_tools(read_only=True)} == {'read_file','search_files'}
workspace_full_tools={t['function']['name']:t['function'] for t in workspace_policy.get_workspace_tools()}
assert set(workspace_full_tools)=={'read_file','search_files','write_file','patch','terminal'}
search_description=workspace_full_tools['search_files']['description'].lower()
assert 'if the user names a file path, including a source module such as discount.py, call read_file with that exact path under /workspace before any search_files call' in search_description,search_description
assert 'search its content once with target=\'content\'' in search_description,search_description
assert 'do not guess test or configuration filenames' in search_description,search_description
for action_tool in ('write_file','patch','terminal'):
 description=workspace_full_tools[action_tool]['description']
 assert 'only on a workspace-action turn' not in description, (action_tool,description)
 assert 'runtime rejects' not in description, (action_tool,description)
# Exercise HADES/Hermes workspace wiring with the available rootful test engine;
# the production runtime gate remains the unmocked rootless check above.
home=Path(__import__('os').environ['HERMES_HOME'])
workspace=Path(__import__('os').environ['HERMES_HOME'])/'workspaces'/'synthetic-owner'; workspace.mkdir(parents=True,mode=0o700)
(workspace/'answer.txt').write_text('ORCHID-9472\n')
workspace_two=Path(__import__('os').environ['HERMES_HOME'])/'workspaces'/'synthetic-owner-two'; workspace_two.mkdir(parents=True,mode=0o700)
(workspace_two/'answer.txt').write_text('VIOLET-6138\n')
(work/'outside.txt').write_text('HOST-SECRET-58')

def create_agent(subject, chat, stream_callback=None):
 return run_agent.AIAgent(
  gateway_session_key=f'hades-user-{subject}', session_id=chat,
  stream_delta_callback=stream_callback or (lambda _chunk: None), base_url='http://127.0.0.1:9/v1',
  api_key='synthetic-only', provider='custom', api_mode='chat_completions',
  model='synthetic-deep-model', enabled_toolsets=[], disabled_toolsets=[],
  quiet_mode=True, skip_context_files=True, skip_memory=True,
  skip_background_review=True, load_soul_identity=False,
 )

agent=create_agent('synthetic-owner','synthetic-unqualified-chat')
hades._hades_original_run_conversation=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('model invoked without rootless sandbox'))
if not real_rootless:
 runtime_denied=agent.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-unqualified-chat')
 assert 'can\'t access project files in this chat' in runtime_denied.get('final_response','').lower(),runtime_denied
 assert runtime_denied.get('api_calls') == 0,runtime_denied
 print('PASS HADES denies workspace activation when only rootful Docker is available')
 workspace_policy.sandbox_runtime_available=lambda: True
 workspace_policy.sandbox_runtime_available=lambda: False
 fallback_agent=create_agent('synthetic-owner','synthetic-diagnosis-fallback')
 fallback_tools=[]
 def ordinary_diagnosis(agent,*args,**kwargs):
  fallback_tools.extend(t['function']['name'] for t in agent.tools)
  prompt=args[0] if args else kwargs.get('user_message','')
  agent._current_turn_id='synthetic-diagnosis-fallback-turn'
  response='I can explain from the details here; paste the test output or code if you want me to inspect it.'
  return {'final_response':response,
   'messages':[{'role':'user','content':prompt},{'role':'assistant','content':response}],
   'current_turn_user_idx':0,
   'turn_id':agent._current_turn_id,
   'api_calls':1,'completed':True}
 hades._hades_original_run_conversation=ordinary_diagnosis
 fallback=fallback_agent.run_conversation('Why is this Python test failing?',task_id='synthetic-diagnosis-fallback')
 assert fallback.get('api_calls') == 1,fallback
 assert 'workspace' not in fallback.get('final_response','').lower() or 'paste' in fallback.get('final_response','').lower(),fallback
 assert not any(n in {'read_file','search_files','write_file','patch','terminal'} for n in fallback_tools),fallback_tools
 print('PASS diagnosis falls back to the model naturally when no rootless workspace is available')
 workspace_policy.sandbox_runtime_available=lambda: True
else:
 print('PASS real rootless sandbox gate is active; workspace action proceeds without a predicate mock')
agent=create_agent('synthetic-owner','synthetic-inspection-chat')
inspection_catalog=[]
inspection_deltas=[]
def native_inspection(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-inspection-turn'
 assert inspection_deltas and inspection_deltas[0] == 'I’ll read the relevant files and explain what I find.\n\n',inspection_deltas
 names={t['function']['name'] for t in agent.tools}
 inspection_catalog.append((names,set(agent.valid_tool_names)))
 assert names == {'read_file','search_files'},names
 assert set(agent.valid_tool_names) == {'read_file','search_files'},agent.valid_tool_names
 from types import SimpleNamespace
 import json
 from agent.tool_executor import _parse_tool_call
 from tools import tool_search
 bridge_payloads={
  tool_search.TOOL_SEARCH_NAME:{'queries':['terminal']},
  tool_search.TOOL_DESCRIBE_NAME:{'names':['terminal']},
  tool_search.TOOL_CALL_NAME:{'calls':[{'name':'terminal','arguments':{'command':'pwd'}}]},
 }
 for bridge_name,bridge_args in bridge_payloads.items():
  blocked=_parse_tool_call(agent,SimpleNamespace(function=SimpleNamespace(
   name=bridge_name,arguments=json.dumps(bridge_args))))
  assert blocked.scope_block and 'not available in this HADES session' in blocked.scope_block,(
   bridge_name,blocked)
 prompt=agent.ephemeral_system_prompt.lower()
 assert 'if the user names a file path, including a source module such as discount.py, call read_file with that exact path under /workspace before any search_files call' in prompt,prompt
 assert "target='files', pattern='*', path='/workspace'" in prompt,prompt
 assert "search its contents directly once with search_files target='content'" in prompt,prompt
 assert "filename glob, not a regex: use '*' for all names, never '.*'" in prompt,prompt
 assert 'this turn is read-only. the only available tools are read_file and search_files' in prompt,prompt
 assert 'do not call terminal, patch, write_file, or any other tool' in prompt,prompt
 assert 'do not execute commands or tests, modify files, or claim that files were changed' in prompt,prompt
 assert 'do not pass a directory to read_file' in prompt,prompt
 assert get_terminal_scope() is not None
 response='The test uses addition where rectangle area requires multiplication.'
 return {'final_response':response,
  'messages':[{'role':'user','content':user_message},
              {'role':'tool','name':'read_file','content':'geometry.py: return width + height'},
              {'role':'assistant','content':response}], 'current_turn_user_idx':0,
  'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}
hades._hades_original_run_conversation=native_inspection
inspection_agent=create_agent('synthetic-owner','synthetic-inspection-chat',inspection_deltas.append)
inspection=inspection_agent.run_conversation('Why is this Python test failing?',task_id='synthetic-inspection-chat')
assert 'addition' in inspection.get('final_response',''),inspection
assert inspection_deltas[-1] == inspection.get('final_response'),inspection_deltas
assert inspection_catalog == [(
 {'read_file','search_files'},
 {'read_file','search_files'},
)],inspection_catalog
assert get_terminal_scope() is None,get_terminal_scope()
print('PASS diagnosis schema and executable-tool boundaries match the selected workspace mode')
calls=[]
terminal_results=[]
action_deltas=[]
def native_read(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-native-read-turn'
 assert action_deltas and action_deltas[0] == 'I’ll inspect the workspace, make the requested change, and verify it before reporting back.\n\n',action_deltas
 names={t['function']['name'] for t in agent.tools}
 assert names == {'read_file','search_files','write_file','patch','terminal'}, names
 assert set(agent.valid_tool_names) == names,agent.valid_tool_names
 prompt=agent.ephemeral_system_prompt.lower()
 assert 'if the user names a file path, including a source module such as discount.py, call read_file with that exact path under /workspace before any search_files call' in prompt,prompt
 assert 'after a successful code patch or write, do not end the turn until a terminal call runs' in prompt,prompt
 assert 'a patch or write result is not test evidence' in prompt,prompt
 assert 'terminal result shows that test completed with exit code 0' in prompt,prompt
 assert "search content once with target='content'" in prompt,prompt
 assert "target='files', pattern='*', path='/workspace'" in prompt,prompt
 assert "filename glob, not a regex: use '*' for all names, never '.*'" in prompt,prompt
 assert 'make one search_files call' in prompt,prompt
 assert 'do not guess test or configuration filenames' in prompt,prompt
 assert 'read the relevant source and test files once' in prompt,prompt
 assert 'inspect the readme, makefile, or equivalent test configuration' in prompt,prompt
 assert 'if the sandbox lacks a wrapper such as make' in prompt,prompt
 assert terminal_env('TERMINAL_ENV') == 'docker'
 assert terminal_env('TERMINAL_DOCKER_NETWORK') == 'false'
 assert terminal_env('TERMINAL_DOCKER_FORWARD_ENV') == '[]'
 assert terminal_env('TERMINAL_DOCKER_IMAGE') == os.environ['HADES_HERMES_SANDBOX_IMAGE']
 assert get_terminal_scope() is not None
 raw=read_file_tool('/workspace/answer.txt',task_id=kwargs['task_id'])
 calls.append(raw)
 token=re.search(r'(?:ORCHID-9472|VIOLET-6138)',raw).group(0)
 if real_rootless:
  from tools.terminal_tool import terminal_tool
  try:
   terminal_result=terminal_tool(
    'pwd && cat /workspace/answer.txt && test ! -e /workspace/outside.txt && cat /proc/net/route',
    task_id=kwargs['task_id'],timeout=60,
   )
   terminal_results.append(__import__('json').loads(terminal_result))
  except Exception as exc:
   terminal_results.append({'exception_type':type(exc).__name__,'exception':str(exc)[:500]})
 response=f'The token is {token}.'
 return {'final_response':response,'messages':[
  {'role':'user','content':user_message},
  {'role':'tool','name':'read_file','content':raw},
  {'role':'assistant','content':response}], 'current_turn_user_idx':0,
  'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}

hades._hades_original_run_conversation=native_read
agent=create_agent('synthetic-owner','synthetic-work-chat',action_deltas.append)
original_action_overrides=dict(agent.request_overrides)
answer=agent.run_conversation('Run a shell command in the workspace and tell me the exact token from answer.txt.',task_id='synthetic-work-chat')
assert 'ORCHID-9472' in answer.get('final_response',''),(answer,calls,terminal_results)
assert action_deltas[-1] == answer.get('final_response'),action_deltas
assert calls and 'ORCHID-9472' in calls[0]
assert 'HOST-SECRET-58' not in calls[0]
if real_rootless:
 assert terminal_results, 'the native terminal tool did not produce a result'
 terminal_data=terminal_results[-1]
 assert terminal_data.get('exit_code') == 0,terminal_data
 terminal_output=terminal_data.get('output','')
 assert '/workspace' in terminal_output and 'ORCHID-9472' in terminal_output,terminal_data
 assert 'HOST-SECRET-58' not in terminal_output,terminal_data
 assert '00000000' not in terminal_output,terminal_data
 print('PASS native Hermes terminal read is rooted at /workspace, cannot see sibling host data, and has no default network route')
assert get_terminal_scope() is None, get_terminal_scope()
assert agent.request_overrides == original_action_overrides,agent.request_overrides
print('PASS HADES exposes only the five native file/shell tools for an authenticated owner workspace turn')
print('PASS HADES binds Hermes Docker cwd to the owner workspace and disables network/env forwarding')

def fabricated_answer(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-fabricated-answer-turn'
 assert {t['function']['name'] for t in agent.tools} == {'read_file','search_files','write_file','patch','terminal'}
 return {'final_response':'I read it; the token is MADE-UP-001.','messages':[
  {'role':'user','content':user_message},
  {'role':'assistant','content':'I read it; the token is MADE-UP-001.'}],
  'current_turn_user_idx':0,'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}

hades._hades_original_run_conversation=fabricated_answer
guarded=agent.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-work-chat')
assert 'couldn\'t verify a workspace tool result' in guarded.get('final_response','').lower(),guarded
assert 'MADE-UP-001' not in guarded.get('final_response',''),guarded
print('PASS HADES suppresses a fabricated workspace result when Hermes returns no tool response')

def fabricated_test_claim(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-fabricated-test-turn'
 return {'final_response':'Both tests passed.','messages':[
  {'role':'user','content':user_message},
  {'role':'assistant','tool_calls':[{'id':'patch-1','type':'function','function':{'name':'patch','arguments':'{}'}}]},
  {'role':'tool','name':'patch','tool_call_id':'patch-1','content':'{"files_modified":["/workspace/geometry.py"]}'},
  {'role':'assistant','content':'Both tests passed.'}],
  'current_turn_user_idx':0,'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}

hades._hades_original_run_conversation=fabricated_test_claim
unverified=agent.run_conversation('Fix the failing test in geometry.py.',task_id='synthetic-work-chat')
assert 'didn\'t receive a successful test result' in unverified.get('final_response','').lower(),unverified
assert 'Both tests passed' not in unverified.get('final_response',''),unverified
assert action_deltas[-1] == unverified.get('final_response'),action_deltas
print('PASS HADES replaces an unsupported passing-test claim after a successful code mutation')

def missing_current_assistant(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-missing-current-assistant-turn'
 prior_user={'role':'user','content':'Explain the earlier failure.'}
 prior_assistant={'role':'assistant','content':'Earlier answer must remain intact.'}
 return {'final_response':'Both tests passed.','messages':[
  prior_user,prior_assistant,{'role':'user','content':user_message},
  {'role':'assistant','tool_calls':[{'id':'patch-2','type':'function','function':{'name':'patch','arguments':'{}'}}]},
  {'role':'tool','name':'patch','tool_call_id':'patch-2','content':'{"files_modified":["/workspace/geometry.py"]}'}],
  'current_turn_user_idx':2,'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}

hades._hades_original_run_conversation=missing_current_assistant
historical_safe=agent.run_conversation('Fix the failing test in geometry.py.',task_id='synthetic-work-chat')
assert 'Earlier answer must remain intact.' in [
 m.get('content') for m in historical_safe.get('messages',[]) if isinstance(m,dict)
],historical_safe
assert historical_safe.get('messages',[])[-1].get('content') == historical_safe.get('final_response'),historical_safe
assert 'didn\'t receive a successful test result' in historical_safe.get('final_response','').lower(),historical_safe
print('PASS current-turn verification notice preserves historical assistant content')

ordinary_prompt_before = agent.ephemeral_system_prompt
def ordinary_chat(agent,user_message,*args,**kwargs):
 assert agent.tools == [],agent.tools
 assert get_terminal_scope() is None,get_terminal_scope()
 assert agent.ephemeral_system_prompt == ordinary_prompt_before
 return {'final_response':'Hey, good to hear from you.','messages':[{'role':'assistant','content':'Hey, good to hear from you.'}], 'api_calls':1,'completed':True}

hades._hades_original_run_conversation=ordinary_chat
ordinary=agent.run_conversation("Hey, how's it going?",task_id='synthetic-work-chat')
assert 'good to hear' in ordinary.get('final_response',''),ordinary
print('PASS a follow-on ordinary turn restores the empty tool catalog and no sandbox scope')

# Contextual workspace continuations must stay on the tool-capable model even
# though the latest words alone do not match the model-routing phrase list.
continuation_agent=create_agent('synthetic-owner','synthetic-fast-lane-continuation')
continuation_agent.model='qwen3.6:35b'
continuation_agent.base_url='http://127.0.0.1:11434/v1'
fast_route_switches=[]
def record_switch(model,provider,*,api_key,base_url):
 fast_route_switches.append((model,provider,base_url))
 continuation_agent.model=model
 continuation_agent.provider=provider
 continuation_agent.api_key=api_key
 continuation_agent.base_url=base_url
continuation_agent.switch_model=record_switch
previous_fast_url=os.environ.get('HADES_FAST_COMPLETION_BASE_URL')
os.environ['HADES_FAST_COMPLETION_BASE_URL']='http://127.0.0.1:11437/v1'
def contextual_workspace_continue(agent,user_message,*args,**kwargs):
 agent._current_turn_id='synthetic-contextual-workspace-turn'
 assert agent.model=='qwen3.6:35b',agent.model
 assert agent.base_url=='http://127.0.0.1:11434/v1',agent.base_url
 assert set(agent.valid_tool_names)=={'read_file','search_files','write_file','patch','terminal'},agent.valid_tool_names
 return {'final_response':'I can continue the workspace task.','messages':[
  {'role':'user','content':user_message},
  {'role':'tool','name':'read_file','content':'The relevant workspace file was read.'},
  {'role':'assistant','content':'I can continue the workspace task.'}],
  'current_turn_user_idx':0,'turn_id':agent._current_turn_id,
  'api_calls':1,'completed':True}
hades._hades_original_run_conversation=contextual_workspace_continue
contextual=continuation_agent.run_conversation(
 'continue',
 conversation_history=[{'role':'user','content':'Why is this Python test failing?'}],
 task_id='synthetic-fast-lane-continuation',
)
if previous_fast_url is None:
 os.environ.pop('HADES_FAST_COMPLETION_BASE_URL',None)
else:
 os.environ['HADES_FAST_COMPLETION_BASE_URL']=previous_fast_url
assert not fast_route_switches,fast_route_switches
assert 'continue the workspace task' in contextual.get('final_response','').lower(),contextual
print('PASS contextual workspace continuation bypasses the completion-only fast route')

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
assert 'can\'t access project files in this chat' in action.get('final_response','').lower(),action
assert 'haven\'t read or changed anything' in action.get('final_response','').lower(),action
assert 'hades deployment' not in action.get('final_response','').lower(),action
assert action.get('api_calls') == 0,action
os.environ['HADES_WORKSPACE_ENABLED']='true'
print('PASS a traceback question stays model-first while a follow-on code action remains safely gated')

hades._hades_original_run_conversation=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('model invoked for unauthorized household workspace'))
household=create_agent('synthetic-household','synthetic-house-chat')
denied=household.run_conversation('Read answer.txt and tell me the exact token.',task_id='synthetic-house-chat')
assert 'can\'t access project files in this chat' in denied.get('final_response','').lower(),denied
assert 'hades' not in denied.get('final_response','').lower(),denied
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
