#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compat="$repo_dir/webui/streaming_compat.py"
dockerfile="$repo_dir/webui/Dockerfile"

grep -Fq 'let s=t.value;if(s.length<5)' "$compat" || {
  echo 'FAIL streaming compatibility patch does not pin the expected upstream expression' >&2
  exit 1
}
grep -Fq 'if(typeof s!=="string")s="";' "$compat" || {
  echo 'FAIL streaming compatibility patch does not fail closed on non-string deltas' >&2
  exit 1
}
grep -Fq 'COPY webui/streaming_compat.py /opt/hades/streaming_compat.py' "$dockerfile" || {
  echo 'FAIL Open WebUI Dockerfile does not include streaming compatibility source' >&2
  exit 1
}
grep -Fq 'python3 /opt/hades/streaming_compat.py' "$dockerfile" || {
  echo 'FAIL Open WebUI Dockerfile does not execute streaming compatibility patch' >&2
  exit 1
}
python3 -m py_compile "$compat"
echo 'PASS Open WebUI streaming compatibility contract'
