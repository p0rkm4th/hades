"""Synthetic Actual-shaped finance fixture for Gamma acceptance.

This is test data only. It exists to prove that the thin sharing policy is
applied to canonical-shaped account/transaction reads at operation time. It
must never be used as a production ledger or a shadow store.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .policy import FinanceSharePolicy


class SyntheticFinanceService:
    def __init__(self, policy: FinanceSharePolicy, accounts: list[dict[str, Any]], transactions: list[dict[str, Any]]):
        self.policy = policy
        self._accounts = deepcopy(accounts)
        self._transactions = deepcopy(transactions)

    def accounts(self, actor: str, groups: Iterable[str] = ()) -> list[dict[str, Any]]:
        return self.policy.filter_canonical_records(actor, self._accounts, groups)

    def transactions(self, actor: str, groups: Iterable[str] = ()) -> list[dict[str, Any]]:
        return self.policy.filter_canonical_records(actor, self._transactions, groups)

    def share_read(self, actor: str, resource_id: str, grantee: str, grantee_kind: str = "user") -> dict[str, Any]:
        return {"status": "SHARED", "grant": self.policy.grant_read(actor, resource_id, grantee, grantee_kind).__dict__}

    def revoke_read(self, actor: str, resource_id: str, grantee: str, grantee_kind: str = "user") -> dict[str, Any]:
        changed = self.policy.revoke_read(actor, resource_id, grantee, grantee_kind)
        return {"status": "REVOKED" if changed else "NOT_SHARED", "resource_id": resource_id}
