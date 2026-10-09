# HADES core upstream refresh — 2026-10-08

This execution-time check supersedes earlier release notes when version or
release status differs. It records authoritative release state and tracked
pins. A current upstream release is not evidence that HADES production runs
that version.

## Owner-facing and core runtime components

| Component | HADES production / candidate record | Latest stable checked 2026-10-08 | Decision |
|---|---|---|---|
| Open WebUI | Production contract 0.11.1; candidate built from review source `148b66e1` with image ID `sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`; tracked candidate pin aligned to 0.11.4 immutable base `ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f` | 0.11.4, published 2026-09-21 | **HOLD production; finish external build provenance, owner UI, LDAP/group, file-picker, and migration/rollback gates.** On 2026-10-08 the rebuilt image passed synthetic private-chat and Channels acceptance; see [`hades-core-open-webui-0114-candidate-acceptance-20261008.md`](hades-core-open-webui-0114-candidate-acceptance-20261008.md). No newer release was listed by the official Releases API. |
| Hermes Agent | Production 0.21.2; candidate metadata now pins archive `https://github.com/NousResearch/hermes-agent/archive/refs/tags/v0.21.6.tar.gz`, SHA-256 `1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8`, commit `818c13be1dc4fd28987e1e881a9408224afd4535` | 0.21.6, published 2026-10-08 | **QUALIFY in staging; HOLD production.** The official release bundles dashboard auth hardening, Git-filter execution protection, and email sender validation. Its notes intentionally defer detailed changes since 0.21.5 until 0.22.0, so do not infer native capability from the large merge count. The upstream Git-spawn security regression passed 25/25 against exact candidate source. |
| Ollama | No current production runtime version was freshly verified or pinned in `config/versions.env`; the previous staging comparison used 0.40.1, but its binary is not present in this checkout | 0.40.2, published 2026-10-08 | **INVESTIGATE deployment provenance; stage 0.40.2 only with isolated model storage and disk headroom.** The official release upgrades models in the background on first use, keeps original copies temporarily for downgrade, and says a future release will remove the backups. This changes model bytes and disk use, so both comparison arms must be rerun with the exact same upgraded model digest and runtime. The official Linux x86_64 archive SHA-256 is `726bee78706c281b0eeef00746efe51a044d71c592c3f0b195820707f31fdf04`. |
| Hindsight | Configured immutable pin `sha256:84ab…9028`; local image OCI labels identify it as 0.9.2 / source `ebad478`. No Hindsight service was running in this environment, so deployed runtime parity is unverified. Prior staged Hermes plugin checkout was integration tag 1.2.1 (`d56c4ac`) with client/embed 0.10.2. | 0.10.3, published 2026-10-08 | **QUALIFY CANDIDATE; HOLD configured production pin.** Exact v0.10.3 image digest `sha256:b5da…e002` passed disposable API/worker recovery and authenticated HADES explicit-memory acceptance with Hermes 0.21.6 plus the exact v0.10.3 plugin source. Alpha retain/correction/fresh typo recall and Beta/Gamma isolation passed. A follow-up log capture found 33 failed retries from unrelated Hermes automatic title-generation tasks against the intentionally unavailable test model; it did not change the memory results, but ordinary-turn auxiliary behavior remains unqualified. Automatic provider retain/prefetch, semantic paraphrase, embedded-daemon mode, and integrated restart acceptance remain open; see [`hades-core-hindsight-0103-candidate-review-20261008.md`](hades-core-hindsight-0103-candidate-review-20261008.md). |

## Other active dependencies checked 2026-10-08

These checks distinguish public source releases from deployed artifact identity.
Several deployed images are digest-pinned but have no matching release label in
the public version contract, so their exact installed versions remain
unverified. Upgrade recommendations below are staging decisions; none promotes
a production image.

| Component | Tracked pin / observed candidate | Current stable source | Decision and relevant change |
|---|---|---|---|
| Grocy | `config/versions.env` pins a LinuxServer image digest without an application release tag; `grocy-mcp==0.2.0` with a full Python lock | Grocy 4.7.1 (2026-09-04); grocy-mcp 0.2.0 | **INVESTIGATE** the pinned image's OCI version label before changing it. Grocy 4.7.1 fixes calendar iCal authentication, non-Latin password login, and API-key auth in subdirectories. grocy-mcp is current. |
| Actual Budget | HADES server/client pair 26.9.0 | 26.10.0 (2026-10-02) | **HOLD** pending finance owner gate and disposable migration/rollback acceptance. Keep server and client paired; no production finance writes are authorized. |
| Agent Zero | Immutable image digest, no release version recorded beside it | 2.13 (2026-09-23) | **INVESTIGATE** image provenance, then compare its remaining bounded operator role against native Hermes computer use before refreshing. Release notes report file-browser, transport, plugin, and stability work; do not promote two operator systems by default. |
| SearXNG | Immutable image record `2026.5.31-7159b8aed` | Official image tag `2026.10.7-6671d89be` (2026-10-07) | **UPDATE candidate** after exact digest resolution and search/freshness regression checks. The current source tag is newer; retain explicit version plus digest. |
| n8n | Private compose input must supply an immutable image; no production Phase 3 credentials or active schedules are recorded | 2.42.5 (2026-10-08) | **HOLD**. Keep schedules inactive while the operation-time identity and resource checks remain incomplete; record the exact staged image digest before any canary. |
| LLDAP | Immutable image digest based on the `stable` tag; release identity is not recorded with the digest | 0.6.3 (2026-04-30) | **INVESTIGATE** the deployed image's OCI version and digest before changing the identity authority. 0.6.3 includes an LDAP dependency security update and compatibility fixes; test authentication and group resolution before any refresh. |
| PaddleOCR / OCR MCP | Staging Dockerfile pins `paddlepaddle==3.2.1` and `paddleocr-mcp[local-cpu]==0.8.5`; final image is an owner-supplied immutable artifact | PaddleOCR 3.7.0 (2026-06-11); PaddlePaddle 3.3.1 (2026-03-26); paddleocr-mcp 0.8.5 (2026-06-11) | **HOLD** pending owner-gated OCR acceptance. The MCP package is current; consider PaddlePaddle 3.3.1 only in a rebuilt disposable image with receipt-image accuracy, CPU, and filesystem/network boundary checks. |
| Playwright MCP | `integrations/browser-access/proxy.py` defaults to `@playwright/mcp@0.0.81` | 0.0.83 (2026-09-28) | **UPDATE candidate** after the existing browser proxy boundary tests. 0.0.83 fixes stale tab/frame binding, browser-close download crashes, and navigation dialogs that could time out. |
| Python MCP SDKs | `integrations/grocy-mcp/requirements.lock`: `mcp==2.2.0`, `fastmcp==4.0.3` | MCP 2.3.0 (2026-10-02); FastMCP 4.1.0 (2026-10-08) | **HOLD pending isolated compatibility run** against Grocy schema filtering, auth scope, preview/cancel, and transport behavior. Refresh the lock only with passing boundary checks. |
| OpenAI SDKs | Workspace replay environment recorded OpenAI Python 2.24.0; no HADES-owned JavaScript SDK lock or direct use was found | Python 3.26.1 and Node 7.30.1 (both 2026-10-08) | **HOLD Python major upgrade** until Hermes 0.21.6 compatibility is demonstrated; pin the installed SDK in the Hermes environment. Node SDK is not a direct HADES dependency. |

Sources: [Grocy 4.7.1](https://github.com/grocy/grocy/releases/tag/v4.7.1), [Actual 26.10.0](https://github.com/actualbudget/actual/releases/tag/v26.10.0), [Agent Zero 2.13](https://github.com/agent0ai/agent-zero/releases/tag/v2.13), [SearXNG image tags](https://hub.docker.com/r/searxng/searxng/tags), [n8n 2.42.5](https://github.com/n8n-io/n8n/releases/tag/n8n%402.42.5), [LLDAP 0.6.3](https://github.com/lldap/lldap/releases/tag/v0.6.3), [PaddleOCR 3.7.0](https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.7.0), [paddleocr-mcp](https://pypi.org/project/paddleocr-mcp/), [Playwright MCP 0.0.83](https://github.com/microsoft/playwright-mcp/releases/tag/v0.0.83), [MCP SDK](https://pypi.org/project/mcp/), [FastMCP](https://pypi.org/project/fastmcp/), [OpenAI Python 3.26.1](https://github.com/openai/openai-python/releases/tag/v3.26.1), and [OpenAI Node 7.30.1](https://github.com/openai/openai-node/releases/tag/v7.30.1).

## Relevant comparative evidence

The same-day clean-worktree synthetic workspace escalation replay is recorded
in [`hades-core-workspace-escalation-comparison-20261008-clean-v2.md`](hades-core-workspace-escalation-comparison-20261008-clean-v2.md).
It used current Hermes 0.21.6 and Ollama 0.40.1 with matched model, context,
sampling, sandbox, and prompts. HADES preserved the explanation/action
boundary and exposed smaller tool schemas, but its median composed task was
slower than PLAIN STACK in two repeats. It is diagnostic evidence only, not
owner preference or a release qualification.

## Authoritative sources

- [Open WebUI v0.11.4](https://github.com/open-webui/open-webui/releases/tag/v0.11.4)
- [Hermes Agent v0.21.6](https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6)
- [Ollama v0.40.2](https://github.com/ollama/ollama/releases/tag/v0.40.2) and its [official release checksum manifest](https://github.com/ollama/ollama/releases/download/v0.40.2/sha256sum.txt)
- [Hindsight v0.10.3](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.3)

## Next actions

1. Reproduce the workspace pair from a clean, reviewable source commit and
   expand the balanced subset; investigate the out-of-catalog mutation attempt
   and fix-turn tool loop.
2. Qualify Hermes 0.21.6 session continuity, MCP refresh, and authenticated
   multi-user UI against the exact candidate artifact. Deferred tool search
   and its owner/household Grocy authorization boundary passed the focused
   candidate runtime check; see
   [`hades-core-hermes-0216-tool-search-scope-review-20261008.md`](hades-core-hermes-0216-tool-search-scope-review-20261008.md).
3. Stage Hindsight 0.10.3 and test native Hermes plugin/process behavior for
   removable HADES compatibility code.
4. Verify the deployed inference runtime's source and version. For 0.40.2,
   stage a separate runtime against isolated model storage, check disk headroom,
   record model digests before and after first load, then rerun both comparison
   arms against that same resulting model and runtime before deciding whether
   to promote it.

The official release API was rechecked on 2026-10-08 after the previous
0.40.1 entry: it reports v0.40.2 as latest stable. The checksum above comes
from that tag's official `sha256sum.txt`. Ollama 0.40.2 has not been staged or
run here, and no production runtime was changed. The Linux archive is about
1.44 GB before model storage; staging it still requires a private isolated
model directory and a disk-space check before first model load.
