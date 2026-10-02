# Homelab compute capability contract

This document describes the public read-model contract. It contains no
installation's physical host names, addresses, hardware inventory, endpoint
URLs, or current capacity. Deployment-specific records belong in private
`hades-infra` configuration.

## Required observations

For each configured compute resource, keep these fields separate:

| Field | Authority | Meaning |
|---|---|---|
| Stable identity | Proxmox or NetBox ID | Joins records without relying on display name or IP |
| Hardware | Private observed capability matrix | Installed CPU/GPU/memory inventory |
| Runtime | Proxmox | Current host/guest state and allocation |
| Availability | Uptime Kuma or live service check | A configured probe responded or failed |
| Inference catalog | Provider-native read API | Models installed at an endpoint |
| Model residency | Provider-native process API | Models currently loaded, if supported |
| Freshness | Source retrieval timestamp | Whether an observation is live, recent, stale, or unknown |

A model file's size does not establish runtime memory requirements. GPU count
does not establish free VRAM, driver health, multi-GPU support, or safe model
placement. HADES must state estimates and missing measurements instead of
claiming a precise fit.

## Placement response

A placement recommendation must consider current endpoint health, host runtime,
GPU model and VRAM, free memory, current model residency, expected model memory,
context/KV-cache overhead, quantization, and multi-GPU behavior. If any required
input is unavailable, report the candidate evidence and the uncertainty. The
read model grants no placement or infrastructure mutation authority.

## Current repository evidence

The optional read-only provider adapter queries Ollama installed model
metadata and current residency, or an OpenAI-compatible endpoint's model
catalog, with source timestamps and bounded errors. Synthetic tests cover
linked NetBox identity, partial provider failure, and unsupported residency.
Catalog reads are not generation probes and do not report free GPU memory.
A direct development-runner probe has exercised approved private provider APIs
and NetBox identity joins. Deployment-specific runtime and owner-acceptance
evidence is maintained in the private infrastructure repository; this static
capability matrix remains inventory evidence only and does not establish
current utilization, free memory, or model placement.

## Private deployment records

Use the private infrastructure repository for physical inventory, source URLs,
identity links, per-host evidence, and current capacity. Public CI should use
synthetic names, RFC 5737 addresses, and generic GPU fixtures only.
