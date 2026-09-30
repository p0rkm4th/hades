"""Thin, synthetic-only finance sharing policy for Gamma."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")

def _id(value: Any, label: str) -> str:
    value = str(value or "").strip()
    if not _ID.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value

@dataclass(frozen=True)
class FinanceGrant:
    resource_id: str
    grantor: str
    grantee: str
    grantee_kind: str
    operation: str = "read"
    state: str = "active"

class FinanceSharePolicy:
    """Evaluate explicit read grants without owning an Actual ledger."""

    def __init__(self, resources: dict[str, str] | None = None, grants: Iterable[FinanceGrant] = ()):
        self._owners = {_id(resource, "resource_id"): _id(owner, "owner") for resource, owner in (resources or {}).items()}
        self._grants: list[FinanceGrant] = list(grants)

    def register_resource(self, resource_id: str, owner: str) -> None:
        resource_id, owner = _id(resource_id, "resource_id"), _id(owner, "owner")
        existing = self._owners.get(resource_id)
        if existing and existing != owner:
            raise ValueError("resource ownership cannot be reassigned")
        self._owners[resource_id] = owner

    def grant_read(self, actor: str, resource_id: str, grantee: str, grantee_kind: str = "user") -> FinanceGrant:
        actor, resource_id, grantee = _id(actor, "actor"), _id(resource_id, "resource_id"), _id(grantee, "grantee")
        if self._owners.get(resource_id) != actor:
            raise PermissionError("only the resource owner may share finance data")
        if grantee_kind not in {"user", "group"}:
            raise ValueError("grantee_kind must be user or group")
        grant = FinanceGrant(resource_id, actor, grantee, grantee_kind)
        self._grants = [g for g in self._grants if not (g.resource_id == resource_id and g.grantee == grantee and g.grantee_kind == grantee_kind)]
        self._grants.append(grant)
        return grant

    def revoke_read(self, actor: str, resource_id: str, grantee: str, grantee_kind: str = "user") -> bool:
        actor, resource_id, grantee = _id(actor, "actor"), _id(resource_id, "resource_id"), _id(grantee, "grantee")
        if self._owners.get(resource_id) != actor:
            raise PermissionError("only the resource owner may revoke finance data")
        changed = False
        updated = []
        for grant in self._grants:
            match = grant.resource_id == resource_id and grant.grantee == grantee and grant.grantee_kind == grantee_kind and grant.state == "active"
            if match:
                grant = FinanceGrant(grant.resource_id, grant.grantor, grant.grantee, grant.grantee_kind, grant.operation, "revoked")
                changed = True
            updated.append(grant)
        self._grants = updated
        return changed

    def can_read(self, actor: str, resource_id: str, groups: Iterable[str] = ()) -> bool:
        actor, resource_id = _id(actor, "actor"), _id(resource_id, "resource_id")
        if self._owners.get(resource_id) == actor:
            return True
        group_set = {_id(group, "group") for group in groups}
        return any(g.resource_id == resource_id and g.operation == "read" and g.state == "active" and ((g.grantee_kind == "user" and g.grantee == actor) or (g.grantee_kind == "group" and g.grantee in group_set)) for g in self._grants)

    def filter_canonical_records(self, actor: str, records: Iterable[dict[str, Any]], groups: Iterable[str] = ()) -> list[dict[str, Any]]:
        return [record for record in records if isinstance(record, dict) and self.can_read(actor, str(record.get("resource_id") or ""), groups)]

    def export_policy(self) -> dict[str, Any]:
        return {"version": 1, "resources": dict(self._owners), "grants": [asdict(g) for g in self._grants]}

    @classmethod
    def from_policy(cls, document: dict[str, Any]) -> "FinanceSharePolicy":
        if not isinstance(document, dict) or document.get("version") != 1:
            raise ValueError("unsupported finance policy version")
        return cls(document.get("resources", {}), [FinanceGrant(**item) for item in document.get("grants", [])])
