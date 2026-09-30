#!/usr/bin/env bash
set -eu

# Synthetic-only policy contract. No Actual server, credentials, balances, or
# real account data are used here.
python - <<'PY'
from integrations.finance_sharing import FinanceSharePolicy, SyntheticFinanceService

owner = "synthetic-owner"
household_a = "synthetic-household-a"
household_b = "synthetic-household-b"
policy = FinanceSharePolicy({
    "owner-checking": owner,
    "owner-card": owner,
    "household-a-account": household_a,
    "shared-rent": owner,
    "shared-grocery": owner,
})
policy.grant_read(owner, "shared-rent", household_a)
policy.grant_read(owner, "shared-grocery", "household", "group")

assert policy.can_read(owner, "owner-checking")
assert not policy.can_read(household_a, "owner-checking")
assert policy.can_read(household_a, "shared-rent")
assert policy.can_read(household_b, "shared-grocery", ["household"])
assert not policy.can_read(household_b, "shared-rent", ["household"])
assert not policy.can_read("admin", "owner-card")

records = [
    {"resource_id": "owner-checking", "balance": 100},
    {"resource_id": "shared-rent", "balance": 200},
    {"resource_id": "shared-grocery", "balance": 300},
]
assert [row["resource_id"] for row in policy.filter_canonical_records(household_a, records)] == ["shared-rent"]
assert [row["resource_id"] for row in policy.filter_canonical_records(household_b, records, ["household"])] == ["shared-grocery"]

assert policy.revoke_read(owner, "shared-rent", household_a)
assert not policy.can_read(household_a, "shared-rent")
assert not policy.can_read(household_a, "shared-rent")  # old-chat/reload remains denied
try:
    policy.grant_read(household_a, "owner-checking", household_b)
except PermissionError:
    pass
else:
    raise AssertionError("non-owner grant succeeded")

round_trip = FinanceSharePolicy.from_policy(policy.export_policy())
assert not round_trip.can_read(household_a, "shared-rent")
assert round_trip.can_read(household_b, "shared-grocery", ["household"])
policy.grant_read(owner, "shared-rent", "household", "group")

service = SyntheticFinanceService(
    policy,
    [
        {"resource_id": "owner-checking", "name": "Owner Checking", "balance": 1000},
        {"resource_id": "shared-rent", "name": "Shared Rent", "balance": 2000},
    ],
    [
        {"resource_id": "owner-checking", "payee": "Private Utility", "amount": 80},
        {"resource_id": "shared-rent", "payee": "Landlord", "amount": 900},
    ],
)
assert [row["resource_id"] for row in service.accounts(household_a)] == []
assert [row["resource_id"] for row in service.accounts(household_b, ["household"])] == ["shared-rent"]
assert [row["payee"] for row in service.transactions(household_b, ["household"])] == ["Landlord"]
assert service.revoke_read(owner, "shared-grocery", "household", "group")["status"] == "REVOKED"
assert service.accounts(household_b, ["household"]) == [{"resource_id": "shared-rent", "name": "Shared Rent", "balance": 2000}]
assert service.accounts(household_a) == []  # revocation/old-session reads are evaluated now

print("PASS synthetic private-by-default finance policy")
print("PASS explicit user/group sharing and immediate revocation")
print("PASS admin and cross-resource privilege collapse denial")
print("PASS canonical-shaped account/transaction reads filter at operation time")
PY
