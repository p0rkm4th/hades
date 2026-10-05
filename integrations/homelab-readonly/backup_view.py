"""Pure presentation for bounded Proxmox backup observations."""

from __future__ import annotations

from collections.abc import Callable


def format_backup_status(
    report: object, bounded_text: Callable[..., str | None]
) -> str:
    """Format bounded Proxmox backup evidence without broad DR claims."""
    if not isinstance(report, dict):
        return "I couldn't read the Proxmox backup status."
    status = str(report.get("status") or "UNKNOWN").upper()
    if status == "NOT_CONFIGURED":
        return "Proxmox backup status isn't configured in HADES, so I can't verify Proxmox backup jobs or tasks."
    if status == "CONFIGURATION_ERROR":
        return "The Proxmox backup read configuration is invalid, so I can't verify backup jobs or tasks."
    endpoints = report.get("endpoints") if isinstance(report.get("endpoints"), list) else []
    if not endpoints:
        return "I couldn't read any Proxmox backup sources, so backup status is unknown."
    sentences = []
    for endpoint in endpoints[:8]:
        if not isinstance(endpoint, dict):
            continue
        source_id = bounded_text(endpoint.get("source_id"), 100) or "configured Proxmox source"
        endpoint_status = str(endpoint.get("status") or "UNKNOWN").upper()
        jobs_status = str(endpoint.get("jobs_status") or "UNKNOWN").upper()
        tasks_status = str(endpoint.get("tasks_status") or "UNKNOWN").upper()
        task_scope = str(endpoint.get("task_scope") or "UNKNOWN").upper()
        visible_guest_count = endpoint.get("visible_guest_count")
        if jobs_status in {"HEALTHY", "PARTIAL"}:
            jobs = endpoint.get("jobs") if isinstance(endpoint.get("jobs"), list) else []
            if jobs:
                if jobs_status == "PARTIAL":
                    sentences.append(
                        f"Proxmox {source_id} reports at least {len(jobs)} visible configured vzdump job(s) in an incomplete listing."
                    )
                else:
                    sentences.append(f"Proxmox {source_id} reports {len(jobs)} configured vzdump job(s).")
            elif jobs_status == "PARTIAL":
                sentences.append(
                    f"Proxmox {source_id} configured vzdump job listing is incomplete; whether any jobs are configured is unknown."
                )
            else:
                sentences.append(f"Proxmox {source_id} reports no configured vzdump jobs.")
            malformed_job_rows = endpoint.get("malformed_job_rows")
            if isinstance(malformed_job_rows, int) and not isinstance(malformed_job_rows, bool) and malformed_job_rows > 0:
                sentences.append(
                    f"The configured backup-job feed contained {malformed_job_rows} malformed row(s); job coverage is incomplete."
                )
        else:
            sentences.append(f"Proxmox {source_id} backup-job configuration is {jobs_status.casefold()}.")
        if tasks_status in {"HEALTHY", "PARTIAL"}:
            tasks = endpoint.get("tasks") if isinstance(endpoint.get("tasks"), list) else []
            unattributed_tasks = endpoint.get("unattributed_tasks") if isinstance(endpoint.get("unattributed_tasks"), list) else []
            if tasks:
                latest = tasks[0]
                task_status = str(latest.get("status") or "UNKNOWN").upper()
                guest_id = latest.get("guest_id")
                guest_text = f" for guest {guest_id}" if isinstance(guest_id, str) else ""
                when = latest.get("finished_at")
                when_text = f" at {when}" if isinstance(when, str) else ""
                sentences.append(f"The latest visible archived vzdump task{guest_text} reported {task_status}{when_text}.")
            elif unattributed_tasks:
                if task_scope == "SELECTED_GUESTS":
                    sentences.append(
                        "No guest-attributed archived task was returned for the selected guest(s) in the bounded recent history."
                    )
                else:
                    sentences.append(
                        "No guest-attributed archived task was returned in the bounded recent history."
                    )
            elif task_scope == "SELECTED_GUESTS":
                sentences.append(
                    "No archived task was returned for the selected guest(s) in the bounded recent history."
                )
            elif task_scope == "PARTIAL":
                sentences.append(
                    "No archived task was returned in the visible guest scope in the bounded recent history."
                )
            elif endpoint_status == "HEALTHY":
                sentences.append("No archived vzdump task appears in the bounded recent task history.")
            else:
                sentences.append("Archived vzdump task history is incomplete.")
        else:
            sentences.append(f"Archived vzdump task history is {tasks_status.casefold()}.")
        malformed_task_rows = endpoint.get("malformed_task_rows")
        if isinstance(malformed_task_rows, int) and not isinstance(malformed_task_rows, bool) and malformed_task_rows > 0:
            sentences.append(
                f"The archived task feed contained {malformed_task_rows} malformed row(s); task history is incomplete."
            )
        if task_scope == "SELECTED_GUESTS":
            count_text = (
                f"{visible_guest_count} selected guest(s)"
                if isinstance(visible_guest_count, int) and not isinstance(visible_guest_count, bool)
                else "selected guests"
            )
            sentences.append(
                f"Task history is limited to {count_text} covered by this read-only token; other guest task history is unknown."
            )
        elif task_scope == "PARTIAL":
            sentences.append(
                "Task history has partial guest coverage under this read-only token; unlisted guest task history is unknown."
            )
        elif task_scope == "NO_GUEST_AUDIT":
            sentences.append(
                "Guest backup task history is unknown because this read-only token has no VM.Audit visibility."
            )
        elif task_scope == "UNKNOWN":
            sentences.append(
                "Guest backup task history is unknown because effective VM.Audit visibility could not be verified."
            )
        unattributed_tasks = endpoint.get("unattributed_tasks") if isinstance(endpoint.get("unattributed_tasks"), list) else []
        if unattributed_tasks and tasks_status in {"HEALTHY", "PARTIAL"}:
            latest = unattributed_tasks[0]
            task_status = str(latest.get("status") or "UNKNOWN").upper()
            when = latest.get("finished_at")
            when_text = f" at {when}" if isinstance(when, str) else ""
            sentences.append(
                "Proxmox also returned an archived vzdump task without a guest ID; "
                f"it reported {task_status}{when_text} and cannot be attributed to a specific guest."
            )
        if endpoint_status == "PARTIAL":
            sentences.append(f"The {source_id} read is partial.")
        elif endpoint_status == "UNAVAILABLE":
            sentences.append(f"The {source_id} backup source is unavailable.")
    sentences.append(
        "This covers Proxmox vzdump records only; it doesn't verify backup contents, other backup systems, off-site custody, or restoreability."
    )
    retrieved_at = bounded_text(report.get("retrieved_at"), 40)
    sentences.append(
        f"Source reads completed at {retrieved_at}."
        if retrieved_at else
        "Source read time is unavailable."
    )
    return " ".join(sentences)
