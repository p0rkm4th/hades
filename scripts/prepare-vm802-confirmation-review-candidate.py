#!/usr/bin/env python3
"""Prepare a private review-only patch for one exact VM 802 overlay."""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

BASE_SHA = "d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a"
CANDIDATE_SHA = "7761d4958e278c9a336e93776a501b5a53e838e482923275f9a85b8b60fb74c7"


def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one {label} block, found {count}")
    return source.replace(old, new, 1)


def build_candidate(source):
    source = replace_once(source,
'''def _hades_turn_identity(user_text, history):
    """Bind confirmation state to the immediately preceding conversation turn."""
    seed = ""
    if isinstance(history, list):
        for item in reversed(history):
            if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content", "")).strip():
                seed = str(item.get("content", ""))
                break
    seed = seed or str(user_text or "")
    return "conversation:" + hashlib.sha256(seed.strip().casefold().encode("utf-8")).hexdigest()[:24]
''',
'''def _hades_turn_identity(user_text, history, conversation_id=""):
    """Bind confirmation state to the server conversation; fail closed if absent."""
    value = str(conversation_id or "").strip()
    if not value:
        return ""
    seed = "session-id:" + value
    return "conversation:" + hashlib.sha256(seed.casefold().encode("utf-8")).hexdigest()[:24]
''', "conversation identity")
    source = replace_once(source,
'''        self._hades_conversation_id = (
            "conversation:" + hashlib.sha256(_agent_first_user.strip().casefold().encode("utf-8")).hexdigest()[:24]
            if _agent_first_user else str(kwargs.get("session_id") or "")
        )
''',
'''        # Only the server-provided session ID distinguishes equal prompts in
        # separate chats. Never derive confirmation identity from transcript text.
        self._hades_conversation_id = str(kwargs.get("session_id") or "").strip()
''', "agent conversation identity")
    source = replace_once(source,
'''        _server_text = _server_user_turns[-1] if _server_user_turns else str(user_message or "")
''',
'''        _server_text = str(user_message or "").strip()
        if not _server_text:
            _server_text = _server_user_turns[-1] if _server_user_turns else ""
''', "current-turn precedence")
    source = replace_once(source,
'''    affirmative = bool(re.search(r"\\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|create it|please do)\\b", lowered))
    if not backup_intent and affirmative:
''',
'''    affirmative = bool(re.search(r"\\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|create it|please do)\\b", lowered))
    negative = bool(re.search(r"\\b(?:no|nope|nah|don't|do not|cancel|never mind)\\b", lowered))
    if not backup_intent and negative:
        if not subject or scope not in {"owner", "household"} or not phase2_session_key:
            return None
        try:
            from integrations.automation import LifecycleStore
            probe_key = f"session:{subject}:{phase2_session_key}"
            probe_store = LifecycleStore(_hades_health_watch_state_path())
            current_pending = probe_store.pending_get(probe_key, subject)
            if (
                current_pending
                and current_pending.get("action")
                and not current_pending.get("completed_response")
                and ((current_pending.get("record") or {}).get("template_id") or current_pending.get("template_id")) == "hades-backup-verification"
            ):
                probe_store.pending_delete(probe_key, subject)
                _HADES_PENDING_PHASE2.pop(probe_key, None)
                return "Okay, I won't run or change that Backup Check. Nothing was changed."
        except Exception:
            return None
        return None
    if not backup_intent and affirmative:
''', "same-chat decline route")
    pattern = re.compile(r'''            if not probe_store\.pending_get\(probe_key, subject\):\n.*?            backup_intent = True\n''', re.DOTALL)
    replacement = '''            if not probe_store.pending_get(probe_key, subject):
                actor_pending = probe_store.pending_for_actor(subject)
                if any(
                    item.get("payload", {}).get("template_id") == "hades-backup-verification"
                    and not item.get("payload", {}).get("completed_response")
                    for item in actor_pending
                ):
                    return "I couldn't match that confirmation to this conversation's current request, so nothing was changed."
                return None
            backup_intent = True
'''
    source, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise ValueError(f"expected one actor-wide Backup Check fallback, found {count}")
    for old, new in (
        ("_hades_turn_identity(_early_text, _early_history)", "_hades_turn_identity(_early_text, _early_history, getattr(self, '_hades_conversation_id', ''))"),
        ("_hades_turn_identity(_server_text, _server_history_for_identity)", "_hades_turn_identity(_server_text, _server_history_for_identity, getattr(self, '_hades_conversation_id', ''))"),
        ("_hades_turn_identity(user_message, _hades_history)", "_hades_turn_identity(user_message, _hades_history, getattr(self, '_hades_conversation_id', ''))"),
    ):
        source = replace_once(source, old, new, "server-session identity call site")
    return source


def write_candidate(output_path, candidate):
    parent = output_path.parent
    if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ValueError("output parent must already exist with private mode 0700")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(output_path, flags, 0o600)
    except FileExistsError:
        raise FileExistsError("output already exists; refusing to overwrite")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(candidate)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise
    os.chmod(output_path, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.active_overlay.is_symlink() or not args.active_overlay.is_file():
        parser.error("active overlay must be a regular file, not a symlink")
    raw = args.active_overlay.read_bytes()
    base = hashlib.sha256(raw).hexdigest()
    if base != BASE_SHA:
        parser.error(f"active overlay SHA-256 mismatch: expected {BASE_SHA}, found {base}")
    try:
        candidate = build_candidate(raw.decode("utf-8")).encode("utf-8")
        ast.parse(candidate, filename=str(args.output))
    except (UnicodeDecodeError, SyntaxError, ValueError) as exc:
        parser.error(f"candidate preparation failed: {exc}")
    digest = hashlib.sha256(candidate).hexdigest()
    if digest != CANDIDATE_SHA:
        parser.error(f"candidate SHA-256 mismatch: expected {CANDIDATE_SHA}, found {digest}")
    try:
        write_candidate(args.output, candidate)
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))
    print(f"base_sha256={base}")
    print(f"candidate_sha256={digest}")
    print("status=PRIVATE_REVIEW_ONLY; no deployment performed")


if __name__ == "__main__":
    sys.exit(main())
