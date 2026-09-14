#!/usr/bin/env bash
set -Eeuo pipefail
command -v sqlite3 >/dev/null 2>&1 || { echo 'FAIL sqlite3 is required'; exit 1; }
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
source_state="$root/source"; backup="$root/backup"; restored="$root/restored"
mkdir -p "$source_state" "$backup" "$restored"
sqlite3 "$source_state/identity.db" <<'SQL'
CREATE TABLE identity(username TEXT PRIMARY KEY, subject_id TEXT UNIQUE, memory_bank TEXT);
INSERT INTO identity VALUES ('alpha','subject-alpha','bank-alpha');
INSERT INTO identity VALUES ('beta','subject-beta','bank-beta');
SQL
sqlite3 "$source_state/memory.db" <<'SQL'
CREATE TABLE memory(subject_id TEXT, marker TEXT, PRIMARY KEY(subject_id, marker));
INSERT INTO memory VALUES ('subject-alpha','alpha-private-marker');
INSERT INTO memory VALUES ('subject-beta','beta-private-marker');
SQL
sqlite3 "$source_state/grocy.db" <<'SQL'
CREATE TABLE stock(product TEXT PRIMARY KEY, quantity INTEGER);
INSERT INTO stock VALUES ('milk',2);
SQL
printf 'conversation-marker-alpha\n' > "$source_state/conversation.marker"
for db in identity.db memory.db grocy.db; do sqlite3 "$source_state/$db" ".backup '$backup/$db'"; done
cp "$source_state/conversation.marker" "$backup/conversation.marker"
rm -rf "$source_state"
mkdir -p "$restored"
cp "$backup"/* "$restored/"
test "$(sqlite3 "$restored/identity.db" "SELECT subject_id FROM identity WHERE username='alpha';")" = subject-alpha
test "$(sqlite3 "$restored/identity.db" "SELECT memory_bank FROM identity WHERE username='beta';")" = bank-beta
test "$(sqlite3 "$restored/memory.db" "SELECT marker FROM memory WHERE subject_id='subject-alpha';")" = alpha-private-marker
test "$(sqlite3 "$restored/memory.db" "SELECT marker FROM memory WHERE subject_id='subject-beta';")" = beta-private-marker
test "$(sqlite3 "$restored/grocy.db" "SELECT quantity FROM stock WHERE product='milk';")" = 2
grep -Fxq conversation-marker-alpha "$restored/conversation.marker"
test "$(sqlite3 "$restored/identity.db" 'PRAGMA integrity_check;')" = ok
test "$(sqlite3 "$restored/memory.db" 'PRAGMA integrity_check;')" = ok
test "$(sqlite3 "$restored/grocy.db" 'PRAGMA integrity_check;')" = ok
echo 'PASS synthetic backup-destroy-restore preserves stable identity and canonical markers'
