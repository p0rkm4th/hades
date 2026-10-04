# Gamma adversarial end-user dogfood checkpoint

Date: 2026-09-21

## Revisions

- HADES implementation baseline: `2d73b7af1c49139ed30bb4c23c9f8a226032c838`
- HADES checkpoint/report: `246ecd05748af5aad54e82dbd0f0884fef21ebdc`
- hades-infra: `42e46e9beb36f449645b6117e38b578e47317d22`
- Pre-dogfood tags: `gamma-adversarial-preflight`, `infra-gamma-adversarial-preflight`

Both worktrees were clean at checkpoint creation. The live Hermes overlay hash matched the repository file and the service was active.

## Evidence completed

Real authenticated browser sessions were used for synthetic Owner, Household A, and Household B identities, including persistent desktop contexts and mobile-sized contexts. Evidence covered:

- shared Grocy reads and concurrent duplicate-safe grocery mutations;
- correction and reversal language, including late reversal honesty;
- receipt review on mobile, uncertain OCR, cancellation, and OCR outage recovery;
- synthetic finance privacy denial and owner-only authority denial;
- self-service server preview, confirmation, sharing, revocation, and canonical cleanup;
- Fast chat during bounded concurrent deep inference provider load;
- Grocy, SearXNG, and OCR dependency failures with unrelated follow-up requests;
- stale-context grocery repair so old turns cannot become a new mutation target.

The focused contract/regression scripts for Grocy, finance denial, turn liveness, capability boundaries, composition, self-service, and homelab control passed.

## Repairs made during adversarial dogfood

- Bare household grocery additions now resolve deterministically instead of falling through to Deep.
- Late grocery reversals no longer claim an undo that was not performed.
- Private-account finance requests deny deterministically for household users.
- Self-service confirmations persist across gateway turns.
- Completed Proxmox deletions reconcile correctly when the guest is already absent.
- Owner Agent Zero outage handling fails locally when the gateway is unavailable.
- Current-turn grocery mutations no longer inherit stale targets from conversation history.

## Final adversarial closure

The Agent Zero dependency row was subsequently tested at the actual Hermes boundary by stopping the published `hades-agent-zero` dependency on Core. Through fresh authenticated DOM conversations:

- owner received a bounded, human-readable outage;
- household remained deterministically denied by policy;
- a fresh unrelated owner Fast chat succeeded;
- the dependency restarted and returned HTTP 200;
- an owner-equivalent bounded request succeeded after recovery.

The first attempted run exposed a harness setup issue: its New Chat helper did not always click the real New Chat link. The test was corrected to verify a blank conversation before measuring follow-up behavior. No product defect was inferred from the contaminated run.

The refreshed local bundles are complete and verified. storage host's `/tank` mount is not available locally and the available SSH identity cannot authenticate to `<PRIVATE_LAN_ADDRESS>`, so copying this newest pair to the remote landing zone remains an infrastructure-preservation follow-up. Existing Gamma rollback custody remains documented on storage host.

Owner direct dogfood remains pending and is not conflated with synthetic acceptance.

## Verdict

Gamma adversarial engineering dogfood is **PASS**. No new P0/P1 product defect remains from the exercised surface. Owner direct dogfood remains pending and is not conflated with this engineering verdict. The final Gamma tag is created only after this checkpoint is committed and verified.
