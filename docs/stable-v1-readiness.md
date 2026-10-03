# Stable V1 readiness

HADES V1 readiness is assessed from reproducible product contracts, supported
installation paths, recovery evidence, and owner acceptance. This public page
contains no deployment host names, resource IDs, endpoint locations, or private
recovery custody details.

## Product readiness

| Area | Status | Remaining contract |
|---|---|---|
| Identity and household boundaries | Synthetic contract coverage | Repeat owner-approved acceptance on the intended deployment |
| Core chat and memory | Product behavior accepted in synthetic tests | Preserve stable identity mapping across restore |
| Shared household services | Synthetic UI coverage | Owner-gated production acceptance |
| Read-only homelab view | PARTIAL | Owner/household UI dogfood and reviewed source links are active; improve partial Proxmox guest visibility and service identity/catalog coverage |
| Inference awareness | PARTIAL | Provider catalogs and residency are deployed and owner-dogfooded; configure the owner-gated fixed-command GPU telemetry before making live capacity comparisons |
| Backup and restore | PARTIAL | Complete synthetic restore proof plus separately managed off-host custody |
| Installation and upgrades | Contract documented | Independent clean-host reproduction and operator acceptance |
| Optional integrations | GATED | Require explicit private inputs and remain disabled when absent |

## Release candidate gate

A V1 release candidate requires a clean supported installation, idempotent
rerun, non-mutating doctor, functional household acceptance, reboot recovery,
and synthetic backup/destroy/restore on independent disposable guests. Public
CI must remain green. Owner approval and private deployment evidence remain
separate gates.

The private infrastructure repository is authoritative for live topology,
provisioning, source credentials, runtime state, and owner-managed recovery
custody. This document does not authorize production migration or cutover.

## Installation evidence

| Capability | Status | Smallest remaining contract |
|---|---|---|
| Installation/rebuild | PARTIAL | Close the generated-installer and independent clean-host reconstruction gates. |

## Stable-v1 readiness score

This score describes public product evidence. Private owner acceptance and
deployment status remain in the private infrastructure records.

| Capability | Status | Smallest remaining contract |
|---|---|---|
| Owner daily-driver | OWNER-GATED | Complete owner-visible acceptance on the intended deployment. |
| Household multi-user | PARTIAL | Complete owner-visible authenticated composition and isolation acceptance. |
| Private memory | PASS | Preserve subject mapping through restore and verify restart persistence. |
| Shared household state | PASS | Retain canonical read-back and persistence coverage for shared workflows. |
| Web/search | OWNER-GATED | Confirm fresh search behavior in authenticated owner use. |
| Bounded operator | PASS | Keep unsafe delegation rejected before upstream dispatch. |
| Finance | OWNER-GATED | Approve canonical environment, credentials, and production scope before writes. |
| Homelab | PARTIAL | Synthetic identity, freshness, conflict, partial-source, and Ollama catalog/residency contracts pass; live source links and authenticated owner dogfood remain. |
| Home Assistant | PARTIAL | Connect only an approved read-only endpoint and entity allowlist. |
| Automation | PARTIAL | Complete owner-approved production authority and recovery acceptance. |
| Recovery | PARTIAL | Complete full synthetic restore and document separate custody policy. |
| Installation/rebuild | PARTIAL | Close independent clean-host reconstruction and repeatability gates. |
| Security | PARTIAL | Preserve fail-closed identity, capability, and secret handling contracts. |
| Performance | PARTIAL | Measure representative owner-facing operations on supported hardware. |

## Source-of-truth adversarial contract

Live operational answers must retain source, identity, and freshness. Missing,
stale, or contradictory sources remain explicit states; caches and memory do
not replace canonical inventory, runtime, or service-native authority.
