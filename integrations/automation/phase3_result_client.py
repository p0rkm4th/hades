"""HADES-only client for requester-scoped Phase 3 result reads."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .phase3_request import RESULTS_PATH, sign_results_request


MAX_RESPONSE_BYTES = 200 * 1024
MAX_RESULTS = 5

_RESULT_INTENT = re.compile(
    r"\b(?:latest|recent|last|previous|my|our|the)\b.{0,48}"
    r"\b(?:automation|summary|summaries|grocery|groceries|inventory|"
    r"server\s+health|backup\s+check|backup\s+verification)\b.{0,48}"
    r"\b(?:result|results|report|reports|find|found|run|went|status|check|summary)\b"
    r"|\bhow\s+did\s+(?:my|our|the)\s+(?:weekly|grocery|inventory|server|backup)"
    r"(?:\s+household)?\s+(?:summary|check|watch|automation)\s+(?:go|look|turn\s+out)\b"
    r"|\bwhat\s+did\s+(?:my|our|the)\s+(?:weekly|grocery|inventory|server|backup)"
    r"(?:\s+household)?\s+(?:summary|check|watch|automation)\s+(?:find|report|say)\b"
    r"|\bwhen\s+(?:was|were)\s+(?:(?:my|our|the)\s+)?backups?\s+(?:last\s+)?(?:checked|verified|run)\b"
    r"|\bwhen\s+did\s+(?:(?:we|i)\s+)?(?:last\s+)?(?:check|verify|run)\s+(?:(?:my|our|the)\s+)?backups?\b"
    r"|\bhow\s+old\s+(?:are|is)\s+(?:(?:my|our|the)\s+)?backups?\b"
    r"|\b(?:are|is)\s+(?:(?:my|our|the)\s+)?backups?\s+(?:current|up\s+to\s+date)\b",
    re.IGNORECASE,
)


def is_phase3_results_intent(text: str) -> bool:
    """Match explicit result-history questions without catching generic chat."""
    value = str(text or "").strip()
    return bool(value and len(value) <= 1000 and _RESULT_INTENT.search(value))


def render_recent_results(results: list[dict]) -> str:
    """Render only bounded, recognized fields from the fixed result catalog."""
    if not results:
        return "There are no completed automation results available for your current access."
    names = {
        "server-health-watch": "Server Health Watch",
        "low-inventory-summary": "Grocery Summary",
        "weekly-household-summary": "Weekly Household Summary",
        "hades-backup-verification": "Backup Check",
    }
    lines = []
    for item in results[:MAX_RESULTS]:
        template = item.get("template_type")
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        title = names.get(template)
        if not title:
            continue
        state = str(result.get("hades_state", result.get("state", ""))).upper()
        if state in {"SOURCE_UNAVAILABLE", "UNAVAILABLE", "UNKNOWN"}:
            detail = "The source was unavailable, so I couldn't confirm a result."
        elif template == "server-health-watch":
            detail = {
                "UP": "HADES Core was reported up.",
                "DOWN": "HADES Core was reported down.",
            }.get(state, "The health result did not include a recognized status.")
        elif template == "low-inventory-summary":
            low = _result_names(result.get("low", []))
            out = _result_names(result.get("out", []))
            no_minimum = _result_names(result.get("no_minimum", []))
            if state not in {"READY", "OK", "COMPLETE"}:
                detail = "The inventory source did not confirm a complete result."
            else:
                detail = f"{len(low)} item(s) below minimum; {len(out)} out of stock."
                if low:
                    detail += " Low: " + ", ".join(low[:3]) + ("…" if len(low) > 3 else ".")
                if no_minimum:
                    detail += f" {len(no_minimum)} item(s) have no minimum set."
        elif template == "hades-backup-verification":
            targets = result.get("targets")
            if isinstance(targets, list):
                target_details = []
                last_successes = result.get("last_success_by_target")
                if not isinstance(last_successes, dict):
                    last_successes = {}
                target_names = {
                    "hades": "HADES repository backup",
                    "infra": "infrastructure repository backup",
                }
                state_text = {
                    "HEALTHY": "healthy",
                    "STALE": "stale; needs attention",
                    "FAILED": "could not be verified; needs attention",
                    "MISSING": "missing; needs attention",
                    "SOURCE_UNAVAILABLE": "backup source unavailable",
                    "UNKNOWN": "status unknown",
                }
                for target in targets[:2]:
                    if not isinstance(target, dict):
                        continue
                    target_id = target.get("target")
                    if not isinstance(target_id, str):
                        continue
                    label = target_names.get(target_id)
                    target_state = str(target.get("hades_state", "")).upper()
                    if not label or target_state not in state_text:
                        continue
                    dates = []
                    artifact_time = _safe_utc_time(target.get("artifact_mtime"))
                    checked_time = _safe_utc_time(target.get("observed_at"))
                    last_good = last_successes.get(target_id)
                    if isinstance(last_good, dict):
                        last_good_artifact = _safe_utc_time(last_good.get("artifact_mtime"))
                        last_good_check = _safe_utc_time(last_good.get("checked_at"))
                        if last_good_check:
                            dates.append(f"last successful check {last_good_check}")
                        if last_good_artifact:
                            dates.append(f"verified copy dated {last_good_artifact}")
                    elif target_state == "HEALTHY" and artifact_time:
                        dates.append(f"verified copy dated {artifact_time}")
                    elif target_state != "HEALTHY":
                        if result.get("last_success_history_truncated") is True:
                            dates.append("no successful check found in the latest 100 results")
                        else:
                            dates.append("no previous successful check recorded")
                    if checked_time:
                        dates.append(f"latest check {checked_time}")
                    suffix = f" ({'; '.join(dates)})" if dates else ""
                    target_details.append(f"{label}: {state_text[target_state]}{suffix}")
                detail = f"Repository backups: {'; '.join(target_details)}" if target_details else "The backup result did not include recognized target statuses."
            else:
                # Older stored results contain only the aggregate state.
                detail = {
                    "HEALTHY": "The backup check reported healthy custody.",
                    "ATTENTION": "The backup check needs attention.",
                    "READY": "The backup check completed.",
                }.get(state, "The backup result did not include a recognized status.")
        else:
            if state in {"READY", "OK", "COMPLETE"}:
                detail = "The household summary completed."
            elif state:
                detail = "The household summary needs attention."
            else:
                detail = "The household summary did not include a recognized status."
        lines.append(f"{title}: {detail}")
    return "\n".join(lines) if lines else "There are no recognized completed results available for your current access."


def actionable_notification_snapshot(results: list[dict]) -> list[dict]:
    """Return bounded, privacy-safe alert state for current authorized results.

    Snapshots include healthy states for transition tracking, but routine
    successes are not alerts. A stable state key suppresses repeat alerts for
    a still-degraded scheduled source while allowing recovery then regression
    to notify again.
    """
    known = {
        "server-health-watch": ("Server Health Watch", {"hades-core.health"}),
        "low-inventory-summary": ("Grocery Summary", {"grocy.household"}),
        "weekly-household-summary": ("Weekly Household Summary", {"hades-core.health", "grocy.household", "backup.evidence"}),
        "hades-backup-verification": ("Backup Check", {"backup.evidence"}),
    }
    bad_backup = {
        "STALE": "stale",
        "FAILED": "could not be verified",
        "MISSING": "missing",
        "SOURCE_UNAVAILABLE": "unavailable",
        "UNKNOWN": "unknown",
        "ATTENTION": "needs attention",
    }
    candidates = []
    latest_by_source: dict[str, tuple[int, dict]] = {}
    for item in results[:MAX_RESULTS] if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        template = item.get("template_type")
        definition = known.get(template)
        scope = item.get("resource_scope")
        completed_at = item.get("completed_at")
        if (
            not definition or not isinstance(scope, list) or not scope
            or any(not isinstance(value, str) for value in scope)
            or not set(scope).issubset(definition[1]) or type(completed_at) is not int
        ):
            continue
        identity = json.dumps([template, sorted(set(scope))], separators=(",", ":"), sort_keys=True)
        source_key = hashlib.sha256(identity.encode()).hexdigest()
        prior = latest_by_source.get(source_key)
        # The query normally arrives newest first. Compare timestamps as well
        # so a reordered response cannot let an old state replace the current
        # one. On equal timestamps, preserve the first row from the stable
        # result ordering.
        if prior is None or completed_at > prior[0]:
            latest_by_source[source_key] = (completed_at, item)
    candidates = [item for _timestamp, item in sorted(latest_by_source.values(), key=lambda row: row[0], reverse=True)]

    output = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        template = item.get("template_type")
        definition = known.get(template)
        scope = item.get("resource_scope")
        result = item.get("result")
        if (
            not definition or not isinstance(scope, list) or not scope or not isinstance(result, dict)
            or any(not isinstance(value, str) for value in scope)
            or not set(scope).issubset(definition[1])
        ):
            continue
        title = definition[0]
        state = str(result.get("hades_state") or result.get("state") or "UNKNOWN").upper()
        message = ""
        actionable = False
        semantic: dict[str, object] = {"state": state}
        if template == "server-health-watch":
            actionable = state in {"DOWN", "UNKNOWN", "SOURCE_UNAVAILABLE", "UNAVAILABLE", "FAILED"}
            if state == "DOWN":
                message = "HADES Core's health check reported down."
            elif actionable:
                message = "The health check could not confirm HADES Core status."
        elif template == "low-inventory-summary":
            low = _result_names(result.get("low", []))
            out = _result_names(result.get("out", []))
            actionable = state in {"SOURCE_UNAVAILABLE", "UNAVAILABLE", "UNKNOWN", "FAILED"} or bool(low or out)
            semantic.update({"low_count": len(low), "out_count": len(out)})
            if low or out:
                message = f"Grocy found {len(low)} item(s) below minimum and {len(out)} out of stock."
            elif actionable:
                message = "The grocery summary could not confirm current stock."
        elif template == "hades-backup-verification":
            targets = result.get("targets")
            bad = []
            if isinstance(targets, list):
                for target in targets[:2]:
                    if not isinstance(target, dict):
                        continue
                    name = {"hades": "HADES repository", "infra": "infrastructure repository"}.get(target.get("target"))
                    target_state = str(target.get("hades_state") or "UNKNOWN").upper()
                    if name and target_state in bad_backup:
                        bad.append((name, bad_backup[target_state]))
            semantic["targets"] = bad
            actionable = bool(bad) or state in {"ATTENTION", "SOURCE_UNAVAILABLE", "UNAVAILABLE", "UNKNOWN", "FAILED"}
            if bad:
                message = "; ".join(f"{name} backup is {status}" for name, status in bad) + "."
            elif actionable:
                message = "The backup check needs attention, but its target details were unavailable."
        else:
            sources = result.get("sources")
            if not isinstance(sources, dict):
                sources = {}
            attention = []
            for key, value in sorted(sources.items()):
                if key not in {"hades-core.health", "grocy.household", "backup.evidence"} or not isinstance(value, dict):
                    continue
                source_state = str(value.get("hades_state") or value.get("state") or "UNKNOWN").upper()
                if source_state in {"PARTIAL", "FAILED", "SOURCE_UNAVAILABLE", "UNAVAILABLE", "UNKNOWN", "ATTENTION"}:
                    attention.append({"hades-core.health": "Server Health", "grocy.household": "Groceries", "backup.evidence": "Backup Verification"}[key])
            semantic["attention_sources"] = attention
            actionable = state in {"PARTIAL", "FAILED", "SOURCE_UNAVAILABLE", "UNAVAILABLE", "UNKNOWN", "ATTENTION"} or bool(attention)
            if attention:
                message = "The household summary could not confirm: " + ", ".join(attention) + "."
            elif actionable:
                message = "The weekly household summary could not confirm all sources."
        identity = json.dumps([template, sorted(set(scope))], separators=(",", ":"), sort_keys=True)
        state_value = json.dumps(semantic, separators=(",", ":"), sort_keys=True)
        output.append({
            "source_key": hashlib.sha256(identity.encode()).hexdigest(),
            "state_key": hashlib.sha256(state_value.encode()).hexdigest(),
            "actionable": bool(actionable),
            "title": title,
            "message": message[:240],
        })
    return output


def _safe_utc_time(value: object) -> str | None:
    """Format only bounded timestamps from the fixed backup result schema."""
    try:
        if type(value) in (int, float):
            if not (0 <= float(value) <= 253402300799):
                return None
            parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
        elif isinstance(value, str) and len(value) <= 40:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            parsed = parsed.astimezone(timezone.utc)
        else:
            return None
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _result_names(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    safe = []
    for entry in value[:20]:
        if isinstance(entry, str):
            name = " ".join(entry.split())[:80]
            if name and not re.search(r"[\r\n\x00-\x1f]", name):
                safe.append(name)
    return safe


class Phase3ResultQueryError(RuntimeError):
    """A bounded, user-safe Phase 3 result query failure."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def _open_without_redirect(request, *, timeout: float):
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def _endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise Phase3ResultQueryError("the HADES result service is unavailable") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != RESULTS_PATH
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise Phase3ResultQueryError("the HADES result service is unavailable")
    if parsed.scheme == "http":
        host = parsed.hostname.casefold()
        if host != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError as exc:
                raise Phase3ResultQueryError("the HADES result service is unavailable") from exc
            if not address.is_private and not address.is_loopback:
                raise Phase3ResultQueryError("the HADES result service is unavailable")
    return value


def _read_key(path_value: str, *, owner_uid: int | None = None) -> bytes:
    if not path_value:
        raise Phase3ResultQueryError("the private HADES result credential is not configured")
    path = Path(path_value)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise Phase3ResultQueryError("the private HADES result credential is unavailable") from exc
    try:
        info = os.fstat(fd)
        expected_uid = os.geteuid() if owner_uid is None else owner_uid
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != expected_uid
            or stat.S_IMODE(info.st_mode) != 0o600
            or not 32 <= info.st_size <= 256
        ):
            raise Phase3ResultQueryError("the private HADES result credential is unavailable")
        value = os.read(fd, 257).rstrip(b"\r\n")
    finally:
        os.close(fd)
    if not 32 <= len(value) <= 256:
        raise Phase3ResultQueryError("the private HADES result credential is unavailable")
    return value


class Phase3ResultClient:
    """Send a server-derived stable subject to the private result endpoint."""

    def __init__(
        self,
        endpoint: str | None = None,
        key_file: str | None = None,
        *,
        timeout: float = 4.0,
        opener=None,
    ):
        raw_endpoint = endpoint if endpoint is not None else os.environ.get(
            "HADES_EPSILON_PHASE3_RESULT_QUERY_URL", "",
        ).strip()
        if not 0.1 <= timeout <= 15:
            raise ValueError("result-query timeout is outside the allowed range")
        self.endpoint = _endpoint(raw_endpoint) if raw_endpoint else ""
        self.key_file = key_file if key_file is not None else os.environ.get(
            "HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE", "",
        ).strip()
        self.timeout = timeout
        self.opener = opener or _open_without_redirect

    def recent_for(self, requester_subject_id: str) -> list[dict]:
        if not self.endpoint:
            raise Phase3ResultQueryError("the HADES result service is not configured")
        if not isinstance(requester_subject_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", requester_subject_id,
        ):
            raise Phase3ResultQueryError("the authenticated HADES identity is unavailable")
        secret = _read_key(self.key_file)
        body = json.dumps(
            {"requester_subject_id": requester_subject_id},
            separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        request = Request(
            self.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-store",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sign_results_request(secret, timestamp, body),
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 403:
                raise Phase3ResultQueryError(
                    "the current account or resource access does not permit these results",
                ) from None
            raise Phase3ResultQueryError("recent HADES results are temporarily unavailable") from None
        except (OSError, URLError, TimeoutError) as exc:
            raise Phase3ResultQueryError("recent HADES results are temporarily unavailable") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise Phase3ResultQueryError("the HADES result response exceeded its fixed bound")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Phase3ResultQueryError("the HADES result service returned an invalid response") from None
        if not isinstance(payload, dict) or set(payload) != {"results"}:
            raise Phase3ResultQueryError("the HADES result service returned an invalid response")
        results = payload["results"]
        if not isinstance(results, list) or len(results) > MAX_RESULTS:
            raise Phase3ResultQueryError("the HADES result service returned an invalid response")
        for item in results:
            if (
                not isinstance(item, dict)
                or set(item) != {"template_type", "resource_scope", "completed_at", "result"}
                or not isinstance(item["template_type"], str)
                or not isinstance(item["resource_scope"], list)
                or type(item["completed_at"]) is not int
                or not isinstance(item["result"], dict)
            ):
                raise Phase3ResultQueryError("the HADES result service returned an invalid response")
        return results
