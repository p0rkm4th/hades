# Gamma selective finance sharing

Finance sharing is synthetic-only in Gamma. Actual Budget remains canonical;
this policy stores only resource ownership and explicit grants, never balances,
transactions, categories, or a shadow ledger.

The policy is private-by-default. A resource owner may grant `read` to one
user or an explicit group and may revoke it. Authorization is evaluated at
operation time from the authenticated subject and current grant state, so an
old conversation, open browser tab, shared Channel, prompt impersonation, or
administrator label cannot preserve revoked access. Administration of grants
does not automatically grant access to private financial contents.

The current Gamma implementation is an authorization-only synthetic policy
contract plus a synthetic Actual-shaped read fixture. The fixture proves that
accounts and transactions are filtered at operation time after share and
revocation, including old-session reads. It is not wired into the owner-gated
production Actual adapter until an explicit Actual budget/account scope and
protected synthetic deployment fixture are selected. No real Scotty finance
data is used.
