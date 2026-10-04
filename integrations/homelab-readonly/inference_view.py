"""Pure inference and GPU response presentation for the homelab read model."""

from __future__ import annotations

import re


def _format_node_activity_fallback(
    user_text: str, summary: dict | None, inference: dict | None = None,
) -> str:
    """Use runtime/inventory evidence when the named machine has no provider link."""
    match = re.search(
        r"\bwhat(?:['’]s|s|\s+is)\s+(?P<target>[a-z0-9][a-z0-9 ._'’-]{0,60}?)\s+"
        r"(?:doing|running)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    target = re.sub(r"[^a-z0-9]+", "", match.group("target").casefold()) if match else ""
    endpoints = inference.get("endpoints", []) if isinstance(inference, dict) else []
    endpoint_matches = [
        endpoint for endpoint in endpoints if isinstance(endpoint, dict)
        and re.sub(
            r"[^a-z0-9]+", "",
            str(endpoint.get("source_identity") or "").removeprefix("inference:").casefold(),
        ) == target
    ]
    if len(endpoint_matches) == 1:
        endpoint = endpoint_matches[0]
        endpoint_state = str(endpoint.get("status") or "UNKNOWN").upper()
        label = " ".join(re.sub(
            r"[._-]+", " ",
            str(endpoint.get("source_identity") or "").removeprefix("inference:"),
        ).split()).title()
        if endpoint_state not in {"READABLE", "PARTIAL"}:
            return (
                f"The configured {label} inference endpoint did not respond to its catalog read. "
                "I can't verify its current model activity, and this doesn't establish whether "
                "the physical host is down."
            )
        response = f"The configured {label} inference endpoint responded to a live catalog read."
        models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
        model_names = list(dict.fromkeys(
            str(model.get("name")) for model in models
            if isinstance(model, dict) and model.get("name")
        ))[:6]
        if model_names:
            response += " Its provider catalog lists " + ", ".join(model_names) + "."
        if endpoint.get("loaded_status") == "CURRENT":
            loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
            loaded_names = list(dict.fromkeys(
                str(model.get("name")) for model in loaded
                if isinstance(model, dict) and model.get("name")
            ))[:6]
            response += " Provider-reported residency: " + (
                ", ".join(loaded_names) if loaded_names else "no models reported loaded"
            ) + "."
        else:
            response += " Current provider-reported residency is unavailable."
        observations = summary.get("availability_summary", []) if isinstance(summary, dict) else []
        target_observations = []
        for observation in observations if isinstance(observations, list) else []:
            if not isinstance(observation, dict):
                continue
            monitor_name = " ".join(str(observation.get("name") or "").split())[:100]
            monitor_key = re.sub(r"[^a-z0-9]+", "", monitor_name.casefold())
            if target and (target in monitor_key or monitor_key in target):
                target_observations.append((monitor_name, observation))
        if len(target_observations) == 1:
            monitor_name, observation = target_observations[0]
            monitor_status = str(observation.get("status") or "unknown").casefold()
            if monitor_status not in {"up", "down", "online", "offline", "unknown"}:
                monitor_status = "unknown"
            freshness = str(observation.get("freshness") or "UNKNOWN").upper()
            response += (
                f" A separate Uptime Kuma check named {monitor_name} reports "
                f"{monitor_status} ({freshness.casefold()} observation)."
            )
            response += (
                " Its record is linked to this machine in the current inventory."
                if _inference_monitor_is_linked_to_target(summary, target, observation)
                else " No stable identity link confirms that this check targets the physical host."
            )
        elif len(target_observations) > 1:
            response += (
                " Multiple similarly named Uptime Kuma checks exist, but none can be "
                "used to establish this machine's reachability without a stable identity link."
            )
        response += (
            " I can't verify that this endpoint belongs to the physical host you named, "
            "or that generation or GPU execution works."
        )
        return response
    resources = summary.get("resources", []) if isinstance(summary, dict) else []
    matches = []
    for resource in resources if isinstance(resources, list) else []:
        if not isinstance(resource, dict):
            continue
        inventory = resource.get("inventory") if isinstance(resource.get("inventory"), dict) else {}
        label = inventory.get("name") or resource.get("name")
        if target and re.sub(r"[^a-z0-9]+", "", str(label or "").casefold()) == target:
            matches.append((resource, inventory, str(label)))
    if len(matches) > 1:
        return "I found multiple inventory records matching that machine, so I can't choose one current status safely."
    if not matches:
        return "I can't match that machine to a current runtime record or linked inference endpoint, so its activity is unknown."
    resource, inventory, label = matches[0]
    runtime_status = str(resource.get("runtime_status") or "UNKNOWN").casefold()
    if runtime_status in {"online", "running"}:
        response = f"Proxmox currently reports {label} {runtime_status}."
    elif runtime_status in {"offline", "stopped"}:
        response = f"Proxmox currently reports {label} {runtime_status}."
    else:
        response = f"I don't have a current Proxmox runtime check for {label}, so I can't say whether it's online."
    role = inventory.get("role")
    if isinstance(role, str) and role.strip():
        response += f" NetBox lists its role as {role.strip()[:120]}."
    conflicts = resource.get("conflicts") if isinstance(resource.get("conflicts"), list) else []
    if conflicts:
        details = [" ".join(str(value).split())[:160] for value in conflicts[:4] if value]
        if details:
            response += " Source disagreement: " + "; ".join(details) + "."
    return response + " No linked inference endpoint provides current model activity for this machine."
def _inference_monitor_is_linked_to_target(
    summary: dict, target: str, observation: dict,
) -> bool:
    source_identity = observation.get("source_identity")
    if not isinstance(source_identity, str) or not source_identity:
        return False
    resources = summary.get("resources", []) if isinstance(summary, dict) else []
    target_canonical_ids = set()
    monitor_canonical_ids = set()
    for resource in resources if isinstance(resources, list) else []:
        if not isinstance(resource, dict):
            continue
        identity = resource.get("identity") if isinstance(resource.get("identity"), dict) else {}
        canonical_id = identity.get("canonical_id")
        if not isinstance(canonical_id, str) or not canonical_id:
            continue
        source_ids = identity.get("source_identities") if isinstance(identity.get("source_identities"), dict) else {}
        kuma_ids = source_ids.get("kuma", [])
        if source_identity in kuma_ids:
            monitor_canonical_ids.add(canonical_id)
        inventory = resource.get("inventory") if isinstance(resource.get("inventory"), dict) else {}
        resource_name = inventory.get("name") or resource.get("name")
        if isinstance(resource_name, str) and re.sub(
            r"[^a-z0-9]+", "", resource_name.casefold(),
        ) == target:
            target_canonical_ids.add(canonical_id)
    return bool(target_canonical_ids & monitor_canonical_ids)


def _inference_resource_names(inventory: dict, summary: dict) -> dict[str, str]:
    """Map canonical NetBox identities to labels from explicitly linked reads."""
    resource_names = {}
    for resource in summary.get("resources", []) if isinstance(summary, dict) else []:
        if not isinstance(resource, dict):
            continue
        identity = resource.get("identity")
        inventory_record = resource.get("inventory")
        if not isinstance(identity, dict) or not isinstance(inventory_record, dict):
            continue
        canonical = identity.get("canonical_id")
        label = inventory_record.get("name") or resource.get("name")
        if isinstance(canonical, str) and canonical and isinstance(label, str) and label.strip():
            resource_names[canonical] = " ".join(label.split())
    for endpoint in inventory.get("endpoints", []) if isinstance(inventory, dict) else []:
        if not isinstance(endpoint, dict) or endpoint.get("identity_status") != "LINKED":
            continue
        canonical = endpoint.get("node_identity")
        label = endpoint.get("node_name")
        if (
            isinstance(canonical, str)
            and re.fullmatch(r"netbox:device:[1-9][0-9]{0,19}", canonical)
            and isinstance(label, str) and label.strip()
        ):
            resource_names[canonical] = " ".join(label.split())
    return resource_names


def resolve_inference_node_target(
    target: str, inventory: dict, summary: dict,
) -> tuple[str, str] | None:
    """Resolve a canonical NetBox label or explicitly linked endpoint alias.

    Provider IDs are lookup aliases only when the inference endpoint has an
    explicit stable NetBox identity link. The returned display name always
    comes from the linked inventory record.
    """
    target_key = re.sub(r"[^a-z0-9]+", "", str(target or "").casefold())
    if not target_key or not isinstance(inventory, dict) or not isinstance(summary, dict):
        return None
    resource_names = _inference_resource_names(inventory, summary)
    matches = {}
    for identity, label in resource_names.items():
        if re.sub(r"[^a-z0-9]+", "", label.casefold()) == target_key:
            matches[identity] = label
    endpoints = inventory.get("endpoints", [])
    for endpoint in endpoints if isinstance(endpoints, list) else []:
        if not isinstance(endpoint, dict) or endpoint.get("identity_status") != "LINKED":
            continue
        identity = endpoint.get("node_identity")
        source_identity = endpoint.get("source_identity")
        if not isinstance(identity, str) or identity not in resource_names:
            continue
        if not isinstance(source_identity, str) or not source_identity.startswith("inference:"):
            continue
        alias_key = re.sub(
            r"[^a-z0-9]+", "", source_identity.removeprefix("inference:").casefold(),
        )
        if alias_key == target_key:
            matches[identity] = resource_names[identity]
    return next(iter(matches.items())) if len(matches) == 1 else None


def format_gpu_hardware_target_response(
    user_text: str, inventory: dict, summary: dict, gpu_telemetry: dict,
) -> str:
    """Resolve a GPU description only through fresh, identity-linked samples."""
    text = str(user_text or "")
    model_match = re.search(
        r"\b(?P<model>(?:rtx|gtx|quadro\s*)?p\s*\d{3,4}|(?:rtx|gtx|a)\s*\d{3,4})s?\b",
        text, re.IGNORECASE,
    )
    qualitative_large = bool(re.search(
        r"\b(?:big|biggest|large|largest)\b.{0,24}\b(?:gpu|graphics\s+cards?)\b.{0,24}\b(?:box|host|machine|server)\b",
        text, re.IGNORECASE,
    ))
    if not model_match and not qualitative_large:
        return "I couldn't identify a GPU hardware description in that question."
    if not all(isinstance(value, dict) for value in (inventory, summary, gpu_telemetry)):
        return "I can't resolve that GPU hardware description because current linked telemetry is unavailable."

    labels = _inference_resource_names(inventory, summary)

    endpoint_rows = inventory.get("endpoints") if isinstance(inventory.get("endpoints"), list) else []
    linked = {}
    complete = bool(endpoint_rows) and len(endpoint_rows) <= 16
    for endpoint in endpoint_rows:
        if not isinstance(endpoint, dict):
            complete = False
            continue
        source_identity = endpoint.get("source_identity")
        canonical_id = endpoint.get("node_identity")
        if (
            endpoint.get("identity_status") != "LINKED"
            or not isinstance(source_identity, str)
            or not source_identity.startswith("inference:")
            or canonical_id not in labels
        ):
            complete = False
            continue
        inference_id = source_identity.removeprefix("inference:")
        if not inference_id or inference_id in linked:
            complete = False
            continue
        linked[inference_id] = (canonical_id, labels[canonical_id])

    telemetry_rows = gpu_telemetry.get("endpoints") if isinstance(gpu_telemetry.get("endpoints"), list) else []
    telemetry_by_id = {}
    for endpoint in telemetry_rows:
        if not isinstance(endpoint, dict):
            complete = False
            continue
        inference_id = endpoint.get("inference_id")
        if not isinstance(inference_id, str) or not inference_id or inference_id in telemetry_by_id:
            complete = False
            continue
        telemetry_by_id[inference_id] = endpoint
    if set(linked) != set(telemetry_by_id):
        complete = False

    candidates = {}
    for inference_id, (canonical_id, label) in linked.items():
        telemetry_endpoint = telemetry_by_id.get(inference_id)
        if not isinstance(telemetry_endpoint, dict) or telemetry_endpoint.get("status") != "READABLE":
            complete = False
            continue
        devices = telemetry_endpoint.get("devices")
        if not isinstance(devices, list) or not devices:
            complete = False
            continue
        if canonical_id in candidates:
            complete = False
            candidates.pop(canonical_id, None)
            continue
        valid_devices = [device for device in devices if isinstance(device, dict) and isinstance(device.get("name"), str)]
        if len(valid_devices) != len(devices):
            complete = False
        candidates[canonical_id] = {
            "label": label,
            "devices": valid_devices,
            "retrieved_at": str(telemetry_endpoint.get("retrieved_at") or gpu_telemetry.get("retrieved_at") or "unknown")[:80],
        }
    if len(candidates) != len(linked) or gpu_telemetry.get("status") != "READABLE":
        complete = False
    if not candidates:
        return "I can't resolve that GPU hardware description because no current identity-linked GPU samples are available."

    if model_match:
        requested_model = re.sub(r"[^a-z0-9]", "", model_match.group("model").casefold()).removeprefix("quadro")
        prefix = text[:model_match.start()]
        count_match = re.search(
            r"\b(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:x|×)?\s*$",
            prefix, re.IGNORECASE,
        )
        count_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                       "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        requested_count = None
        if count_match:
            value = count_match.group("count").casefold()
            requested_count = count_words.get(value, int(value) if value.isdigit() else None)
        matches = []
        for record in candidates.values():
            devices = [device for device in record["devices"]
                       if requested_model in re.sub(r"[^a-z0-9]", "", device["name"].casefold())]
            if devices and (requested_count is None or len(devices) == requested_count):
                matches.append((record, devices))
        if not complete:
            if matches:
                return "I found a current identity-linked GPU match, but some configured GPU sources or identity links are incomplete, so I can't confirm it is the only matching host."
            return "I can't safely identify that GPU model from current telemetry because some configured sources or identity links are incomplete."
        if len(matches) != 1:
            if matches:
                names = ", ".join(sorted({record["label"] for record, _ in matches}))
                return f"More than one linked host matches that GPU description ({names}); I can't choose one uniquely."
            count_text = f"{requested_count} " if requested_count is not None else ""
            return f"No current identity-linked GPU telemetry reports {count_text}{model_match.group('model').strip()} as requested."
        record, devices = matches[0]
        return (f"Current NVIDIA host telemetry identifies {record['label']} with {len(devices)} "
                f"{devices[0]['name']} GPU{'s' if len(devices) != 1 else ''}. Checked at {record['retrieved_at']}. "
                "This is a live hardware query, not proof that a workload completed.")

    if not complete:
        return "I can't safely identify the largest GPU host because one or more configured GPU sources or identity links are incomplete."
    ranked = []
    for record in candidates.values():
        totals = [device.get("memory_total_mib") for device in record["devices"]]
        if any(not isinstance(total, int) for total in totals):
            return "I can't compare the configured GPU hosts because installed GPU memory is missing from a current sample."
        ranked.append((sum(totals), record))
    maximum = max(total for total, _ in ranked)
    largest = [record for total, record in ranked if total == maximum]
    if len(largest) != 1:
        names = ", ".join(sorted(record["label"] for record in largest))
        return f"The largest reported GPU-memory totals are tied across {names}; I can't identify one big GPU box uniquely."
    record = largest[0]
    models = ", ".join(sorted({device["name"] for device in record["devices"]}))
    readings = []
    for device in sorted(record["devices"], key=lambda item: item.get("index") if isinstance(item.get("index"), int) else -1):
        index = device.get("index")
        detail = f"GPU {index}" if isinstance(index, int) else "GPU"
        model = str(device.get("name") or "").strip()
        if model:
            detail += f" ({model[:80]})"
        utilization = device.get("gpu_utilization_percent")
        detail += f": {utilization}% utilization" if isinstance(utilization, int) else ": utilization unavailable"
        free, total = device.get("memory_free_mib"), device.get("memory_total_mib")
        detail += f", {free} MiB free of {total} MiB" if isinstance(free, int) and isinstance(total, int) else ", free VRAM unavailable"
        readings.append(detail)
    total_gpus = len(record["devices"])
    return (f"If by ‘big GPU box’ you mean the linked host with the most installed GPU memory, current telemetry points to "
            f"{record['label']}: {total_gpus} GPU{'s' if total_gpus != 1 else ''} ({models}), {maximum} MiB across those cards. "
            f"That memory is across separate devices, not one shared pool. Current per-card readings: {'; '.join(readings[:32])}. "
            f"Checked at {record['retrieved_at']}. A responding NVIDIA query is not proof that a workload completed.")


def format_inference_inventory_response(
    user_text: str, inventory: dict, summary: dict, gpu_telemetry: dict | None = None,
) -> str:
    """Present bounded current model inventory without overstating health or fit."""
    ai_availability = bool(re.search(
        r"\b(?:can|could)\s+(?:we|i)\s+use\s+(?:the\s+)?(?:ai|artificial intelligence)\b|"
        r"\b(?:is|are)\s+(?:the\s+)?(?:ai|artificial intelligence)\b.{0,35}"
        r"\b(?:working|available|online|up|down|healthy|responding)\b|"
        r"\b(?:ai|artificial intelligence)\b.{0,30}"
        r"\b(?:thing|system|service|server|model|models?)\b.{0,40}"
        r"\b(?:working|available|online|up|down|healthy|responding)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    node_activity = re.search(
        r"\bwhat(?:['’]s|s|\s+is)\s+(?P<target>[a-z0-9][a-z0-9 ._'’-]{0,60}?)\s+"
        r"(?:doing|running)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    gpu_availability_intent = bool(re.search(
        r"\b(?:which|what)\b.{0,35}\b(?:gpus?|graphics cards?)\b.{0,35}\b(?:free|available|capacity|memory|room|load|utili[sz]ation)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    placement_intent = bool(re.search(
        r"\b(?:will|would|can|could)\s+(?:a\s+)?\d+(?:\.\d+)?\s*(?:gb|gib)\s+model\b.{0,50}\b(?:fit|run|work)\b|"
        r"\b(?:will|would|can|could)\b.{0,80}\b(?:fit|run|host|handle)\b.{0,50}\d+(?:\.\d+)?\s*(?:gb|gib)(?:\s+(?:sized\s+)?model)?\b|"
        r"\bwhere\s+should\s+i\s+(?:run|host|put)\b|"
        r"\b(?:what|which)\s+(?:machine|server|gpu)\b.{0,35}\b(?:should|can|has room|have room)\b.{0,45}\b(?:model|workload)\b|"
        r"\b(?:can|could)\b.{0,60}\b(?:handle|fit|run|host)\b.{0,35}\b(?:another|new|\d+\s*(?:gb|b)|model|workload)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    compare_capacity_intent = bool(re.search(
        r"\bcompare\s+current\s+model\s+residency\s+and\s+gpu\s+capacity\s+on\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    natural_capacity_comparison = bool(re.search(
        r"\bwhich\s+(?:one\s+)?(?:has\s+)?more\s+room\b|"
        r"\bwhich\s+(?:host|machine|server|gpu)\b.{0,45}\b(?:has|have)\s+more\s+(?:room|capacity)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    capacity_unknown = (
        "I can't verify current GPU capacity because live per-host GPU utilization and free-VRAM "
        "telemetry is unavailable. Model catalogs and hardware inventory do not establish available capacity."
    )
    if not isinstance(inventory, dict):
        if gpu_availability_intent or placement_intent:
            return capacity_unknown
        if node_activity:
            return _format_node_activity_fallback(user_text, summary, inventory)
        return "I couldn't read the configured inference inventory, so I can't verify model availability right now."
    status = str(inventory.get("status") or "UNKNOWN")
    endpoints = inventory.get("endpoints") if isinstance(inventory.get("endpoints"), list) else []
    if status == "NOT_CONFIGURED":
        if gpu_availability_intent or placement_intent:
            return capacity_unknown
        if ai_availability:
            return "No provider-native AI endpoint is configured, so I can't check whether it is responding."
        if node_activity:
            return _format_node_activity_fallback(user_text, summary, inventory)
        return "Provider-native model inventory is not configured here, so I can't verify which models are installed or loaded."
    if not endpoints:
        if gpu_availability_intent or placement_intent:
            return capacity_unknown
        if ai_availability:
            return "I couldn't check whether the configured AI endpoints are responding because no endpoint results were returned."
        if node_activity:
            return _format_node_activity_fallback(user_text, summary, inventory)
        return "I couldn't read any configured model endpoints, so I can't verify model availability right now."

    if gpu_availability_intent:
        telemetry = gpu_telemetry if isinstance(gpu_telemetry, dict) else {}
        telemetry_endpoints = telemetry.get("endpoints") if isinstance(telemetry.get("endpoints"), list) else []
        if telemetry.get("status") in {"READABLE", "PARTIAL"}:
            gpu_resource_names = _inference_resource_names(inventory, summary)
            labels_by_id = {}
            for provider_endpoint in endpoints:
                if not isinstance(provider_endpoint, dict):
                    continue
                source_identity = str(provider_endpoint.get("source_identity") or "")
                if source_identity.startswith("inference:"):
                    labels_by_id[source_identity.removeprefix("inference:")] = gpu_resource_names.get(
                        provider_endpoint.get("node_identity"), provider_endpoint.get("id")
                    )
            reports = []
            for endpoint in telemetry_endpoints[:16]:
                if not isinstance(endpoint, dict):
                    continue
                host_label = labels_by_id.get(endpoint.get("inference_id")) or str(endpoint.get("inference_id") or "configured host")
                if endpoint.get("status") != "READABLE":
                    reports.append(f"{host_label}: live GPU telemetry unavailable")
                    continue
                devices = endpoint.get("devices") if isinstance(endpoint.get("devices"), list) else []
                for device in devices[:32]:
                    if not isinstance(device, dict):
                        continue
                    free = device.get("memory_free_mib")
                    total = device.get("memory_total_mib")
                    utilization = device.get("gpu_utilization_percent")
                    detail = f"{host_label} GPU {device.get('index')}: "
                    detail += f"{free} MiB free of {total} MiB" if isinstance(free, int) and isinstance(total, int) else "free VRAM unavailable"
                    detail += f", {utilization}% utilization" if isinstance(utilization, int) else ", utilization unavailable"
                    reports.append(detail)
            if reports:
                checked_at = str(telemetry.get("retrieved_at") or "check time unavailable")
                prefix = "Live read-only GPU telemetry (checked " + checked_at + "): " + "; ".join(reports[:24]) + "."
                if telemetry.get("status") == "PARTIAL":
                    prefix += " Some configured endpoints could not be read."
                return prefix + " This is a point-in-time sample; it doesn't guarantee a model will fit or stay resident, because runtime memory depends on model, quantization, context, and workload."
        return (
            "I can't verify which GPUs are free right now. Live GPU utilization and free-VRAM "
            "telemetry is not connected or currently unavailable. A hardware inventory or empty model-residency "
            "report does not establish available capacity."
        )

    resource_names = _inference_resource_names(inventory, summary)

    if compare_capacity_intent or natural_capacity_comparison:
        requested = [
            (label, identity) for identity, label in resource_names.items()
            if isinstance(label, str) and re.search(
                r"(?<![\w])" + re.escape(label) + r"(?![\w])",
                str(user_text or ""), re.IGNORECASE,
            )
        ]
        if len(requested) != 2 and compare_capacity_intent:
            return "I can't compare those hosts from the current context because I couldn't resolve exactly two inventory identities."
        if len(requested) == 2:
            details = []
            provider_by_node = {}
            for label, identity in requested:
                linked = [
                    endpoint for endpoint in endpoints[:16]
                    if isinstance(endpoint, dict) and endpoint.get("node_identity") == identity
                ]
                if len(linked) != 1:
                    details.append(f"{label}: no unambiguous linked inference endpoint")
                    continue
                endpoint = linked[0]
                provider_by_node[identity] = endpoint
                if endpoint.get("status") not in {"READABLE", "PARTIAL"}:
                    details.append(f"{label}: inference endpoint unavailable")
                    continue
                if endpoint.get("loaded_status") == "CURRENT":
                    loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
                    names = list(dict.fromkeys(
                        str(model.get("name")) for model in loaded
                        if isinstance(model, dict) and model.get("name")
                    ))[:5]
                    details.append(f"{label}: provider reports " + ("no models loaded" if not names else "loaded: " + ", ".join(names)))
                else:
                    details.append(f"{label}: current loaded-model state unavailable")
            telemetry = gpu_telemetry if isinstance(gpu_telemetry, dict) else {}
            readings_by_host = {}
            telemetry_endpoints = telemetry.get("endpoints") if isinstance(telemetry.get("endpoints"), list) else []
            for sample in telemetry_endpoints[:16]:
                if not isinstance(sample, dict) or sample.get("status") != "READABLE":
                    continue
                inference_id = str(sample.get("inference_id") or "")
                provider = next((
                    endpoint for endpoint in provider_by_node.values()
                    if str(endpoint.get("source_identity") or "").removeprefix("inference:") == inference_id
                ), None)
                if not isinstance(provider, dict):
                    continue
                label = resource_names.get(provider.get("node_identity"))
                devices = sample.get("devices") if isinstance(sample.get("devices"), list) else []
                for device in devices[:32]:
                    if not isinstance(device, dict):
                        continue
                    readings_by_host.setdefault(label, []).append(device)
            for label, _identity in requested:
                devices = readings_by_host.get(label, [])
                if devices:
                    formatted = []
                    for device in devices:
                        detail = f"GPU {device.get('index')}: "
                        free = device.get("memory_free_mib")
                        total = device.get("memory_total_mib")
                        detail += f"{free} MiB free of {total} MiB" if isinstance(free, int) and isinstance(total, int) else "free VRAM unavailable"
                        utilization = device.get("gpu_utilization_percent")
                        detail += f", {utilization}% utilization" if isinstance(utilization, int) else ", utilization unavailable"
                        formatted.append(detail)
                    details.append(f"{label} live GPU sample: " + ", ".join(formatted))
            response = "; ".join(details) + "."
            if len(readings_by_host) == len(requested):
                free_samples = [
                    (device.get("memory_free_mib"), label)
                    for label in readings_by_host
                    for device in readings_by_host[label]
                    if isinstance(device.get("memory_free_mib"), int)
                ]
                if free_samples:
                    highest_free, highest_label = max(free_samples, key=lambda sample: sample[0])
                    response += (
                        f" At this check, {highest_label} has the highest single-GPU free-VRAM reading "
                        f"({highest_free} MiB)."
                    )
                response += " These are point-in-time readings and don't guarantee model fit."
                if telemetry.get("status") == "PARTIAL":
                    response += " GPU telemetry is partial, so this comparison may omit a host."
            elif readings_by_host:
                response += " This GPU telemetry is incomplete for the two-host comparison, so I can't rank their available capacity."
            else:
                freshness = str(telemetry.get("status") or "NOT_CONFIGURED").casefold().replace("_", " ")
                response += f" Live per-host GPU telemetry is {freshness}, so I can't tell which host has more capacity."
            return response + " Model runtime memory also depends on quantization, context, KV cache, and workload."

    if node_activity:
        requested_node = re.sub(r"[^a-z0-9]+", "", node_activity.group("target").casefold())
        matching_nodes = [
            (identity, label) for identity, label in resource_names.items()
            if isinstance(label, str)
            and re.sub(r"[^a-z0-9]+", "", label.casefold()) == requested_node
        ]
        if len(matching_nodes) != 1:
            return _format_node_activity_fallback(user_text, summary, inventory)
        node_identity, label = matching_nodes[0]
        linked = [
            endpoint for endpoint in endpoints[:16]
            if isinstance(endpoint, dict) and endpoint.get("node_identity") == node_identity
        ]
        if len(linked) != 1:
            return _format_node_activity_fallback(user_text, summary, inventory)
        endpoint = linked[0]
        if endpoint.get("status") != "READABLE":
            return f"The inference endpoint linked to {label} is not responding to its catalog read, so I can't verify its model activity."
        models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
        loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
        names = list(dict.fromkeys(
            str(model.get("name")) for model in models
            if isinstance(model, dict) and model.get("name")
        ))[:10]
        result = f"The inference endpoint linked to {label} is responding."
        provider_checked_at = str(endpoint.get("checked_at") or "").strip()
        if provider_checked_at:
            result += f" Provider API read at {provider_checked_at[:80]}."
        result += " Provider catalog lists " + (", ".join(names) if names else "no installed models") + "."
        if endpoint.get("loaded_status") == "CURRENT":
            loaded_names = list(dict.fromkeys(
                str(model.get("name")) for model in loaded
                if isinstance(model, dict) and model.get("name")
            ))[:8]
            result += " Provider-reported residency: " + (
                ", ".join(loaded_names) if loaded_names else "no loaded models reported"
            ) + "."
        else:
            result += " Current loaded-model state is unavailable."
        # The operator matrix is historical hardware/role context only. Join
        # it by an exact normalized display label, and suppress ambiguous rows.
        capability_rows = summary.get("capability_machines", []) if isinstance(summary, dict) else []
        capability_matches = [
            row for row in capability_rows if isinstance(row, dict)
            and re.sub(r"[^a-z0-9]+", "", str(row.get("name") or "").casefold())
            == re.sub(r"[^a-z0-9]+", "", str(label).casefold())
        ] if isinstance(capability_rows, list) else []
        if len(capability_matches) == 1:
            machine = capability_matches[0]
            facts = []
            role = machine.get("role")
            cpu = machine.get("cpu")
            ram = machine.get("ram_gib")
            gpus = machine.get("gpus")
            if isinstance(role, str) and role.strip():
                facts.append(f"role: {role.strip()[:100]}")
            if isinstance(cpu, str) and cpu.strip():
                facts.append(f"CPU: {cpu.strip()[:120]}")
            if isinstance(ram, (int, float)) and not isinstance(ram, bool) and ram > 0:
                facts.append(f"RAM: {ram:g} GiB")
            if isinstance(gpus, list):
                gpu_names = [" ".join(str(value).split())[:100] for value in gpus[:8] if isinstance(value, str) and value.strip()]
                if gpu_names:
                    # Matrix entries may already carry an observed GPU count
                    # (for example, "4x Quadro P4000"); do not infer a second
                    # count from the number of descriptive strings.
                    facts.append("recorded GPUs: " + ", ".join(gpu_names))
            if facts:
                observed_at = str(summary.get("capability_observed_at") or "time unavailable")[:80]
                freshness = str(summary.get("capability_freshness") or "UNKNOWN").upper()
                if freshness not in {"FRESH", "STALE", "UNKNOWN"}:
                    freshness = "UNKNOWN"
                result += (
                    f" Recorded hardware inventory (observed {observed_at}; "
                    f"freshness {freshness.casefold()}): " + "; ".join(facts)
                    + "; this is not live utilization."
                )
        telemetry_rows = gpu_telemetry.get("endpoints", []) if isinstance(gpu_telemetry, dict) else []
        inference_id = str(endpoint.get("source_identity") or "").removeprefix("inference:")
        telemetry_matches = [
            row for row in telemetry_rows if isinstance(row, dict)
            and row.get("inference_id") == inference_id
        ] if isinstance(telemetry_rows, list) else []
        per_device_utilization_reported = False
        gpu_sample_state = "MISSING"
        if len(telemetry_matches) == 1:
            sample = telemetry_matches[0]
            checked_at = str(sample.get("retrieved_at") or gpu_telemetry.get("retrieved_at") or "time unavailable")[:80]
            if sample.get("status") == "READABLE":
                gpu_sample_state = "READABLE"
                devices = sample.get("devices") if isinstance(sample.get("devices"), list) else []
                readings = []
                for device in devices[:16]:
                    if not isinstance(device, dict):
                        continue
                    detail = str(device.get("name") or "GPU")[:80]
                    free, total = device.get("memory_free_mib"), device.get("memory_total_mib")
                    if isinstance(free, int) and isinstance(total, int):
                        detail += f" {free} MiB free of {total} MiB"
                    utilization = device.get("gpu_utilization_percent")
                    if isinstance(utilization, int):
                        detail += f", {utilization}% utilization"
                        per_device_utilization_reported = True
                    readings.append(detail)
                if readings:
                    result += f" Live host GPU sample ({checked_at}): " + "; ".join(readings) + "."
            else:
                gpu_sample_state = "UNAVAILABLE"
                result += f" Live GPU telemetry was unavailable at {checked_at}."
        caveats = [
            "These source-specific point-in-time observations do not prove a successful generation or overall host health."
        ]
        if endpoint.get("loaded_status") == "CURRENT":
            caveats.append("Provider-reported residency does not prove GPU execution.")
        if gpu_sample_state == "READABLE":
            caveats.append(
                "Host CPU load and sustained utilization are not measured."
                if per_device_utilization_reported
                else "This GPU sample returned no per-device utilization; host CPU load and sustained utilization are not measured."
            )
        elif gpu_sample_state == "UNAVAILABLE":
            caveats.append("Host CPU load and sustained utilization are not measured.")
        else:
            caveats.append("No linked live GPU sample was available; host CPU load and sustained utilization are not measured.")
        return result + " " + " ".join(caveats)

    if placement_intent:
        candidates = []
        capability_machines = (
            summary.get("capability_machines", []) if isinstance(summary, dict) else []
        )
        capabilities = {
            re.sub(r"[^a-z0-9]+", "", str(machine.get("name") or "").casefold()): machine
            for machine in capability_machines if isinstance(machine, dict)
        }
        for endpoint in endpoints[:16]:
            if (
                not isinstance(endpoint, dict)
                or endpoint.get("status") not in {"READABLE", "PARTIAL"}
            ):
                continue
            label = resource_names.get(endpoint.get("node_identity"))
            if not isinstance(label, str) or not label:
                continue
            key = re.sub(r"[^a-z0-9]+", "", label.casefold())
            machine = capabilities.get(key, {})
            role = " ".join(str(machine.get("role") or "").split())[:120]
            loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
            loaded_state = endpoint.get("loaded_status")
            models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
            gpu_rows = machine.get("gpus") if isinstance(machine.get("gpus"), list) else []
            gpu_names = []
            for gpu in gpu_rows:
                if isinstance(gpu, str):
                    gpu_names.append(gpu)
                elif isinstance(gpu, dict) and (gpu.get("model") or gpu.get("name")):
                    count = gpu.get("count")
                    prefix = f"{count} × " if isinstance(count, int) and 1 < count < 129 else ""
                    gpu_names.append(prefix + str(gpu.get("model") or gpu.get("name")))
            candidates.append((
                label, role, gpu_names[:5], str(summary.get("capability_freshness") or "UNKNOWN").upper(),
                loaded, loaded_state, models, str(endpoint.get("status") or "UNKNOWN").upper(),
            ))
        if not candidates:
            return (
                "I can't recommend an inference host from the current reads: no responding "
                "provider endpoint is linked to a named inventory device."
            )
        endpoint_details = []
        hardware_freshness = str(
            summary.get("capability_freshness") or "UNKNOWN"
        ).upper()
        hardware_current = hardware_freshness in {"CURRENT", "FRESH"}
        for label, role, gpu_names, _freshness, loaded, loaded_state, models, endpoint_status in candidates:
            detail = label
            if endpoint_status == "PARTIAL":
                detail += "; provider read is partial"
            catalog_names = list(dict.fromkeys(
                str(model.get("name")) for model in models
                if isinstance(model, dict) and model.get("name")
            ))[:5]
            if catalog_names:
                detail += "; catalog lists: " + ", ".join(catalog_names)
            if hardware_current and role:
                detail += f" (recorded role: {role}"
                if gpu_names:
                    detail += "; hardware inventory: " + ", ".join(gpu_names)
                detail += ")"
            if loaded_state == "CURRENT":
                names = [
                    str(model.get("name")) for model in loaded
                    if isinstance(model, dict) and model.get("name")
                ]
                detail += "; provider reports " + (
                    "no models loaded" if not names else "loaded: " + ", ".join(names[:5])
                )
            else:
                detail += "; loaded-model state unavailable"
            endpoint_details.append(detail)
        response = "Responding inference endpoints: " + "; ".join(endpoint_details[:8]) + "."
        if not hardware_current:
            response += " Hardware role/capability inventory is " + hardware_freshness.casefold() + "."
        telemetry = gpu_telemetry if isinstance(gpu_telemetry, dict) else {}
        live_readings = []
        telemetry_endpoints = telemetry.get("endpoints") if isinstance(telemetry.get("endpoints"), list) else []
        for telemetry_endpoint in telemetry_endpoints[:16]:
            if not isinstance(telemetry_endpoint, dict) or telemetry_endpoint.get("status") != "READABLE":
                continue
            inference_id = telemetry_endpoint.get("inference_id")
            provider_endpoint = next((
                endpoint for endpoint in endpoints
                if isinstance(endpoint, dict)
                and str(endpoint.get("source_identity") or "").removeprefix("inference:") == inference_id
            ), None)
            label = resource_names.get(provider_endpoint.get("node_identity")) if isinstance(provider_endpoint, dict) else None
            if not isinstance(label, str) or not label:
                continue
            devices = telemetry_endpoint.get("devices") if isinstance(telemetry_endpoint.get("devices"), list) else []
            for device in devices[:32]:
                if isinstance(device, dict) and isinstance(device.get("memory_free_mib"), int):
                    live_readings.append((device["memory_free_mib"], label, device.get("index"), device.get("gpu_utilization_percent")))
        if live_readings:
            free_mib, label, gpu_index, utilization = max(live_readings, key=lambda row: row[0])
            checked_at = str(telemetry.get("retrieved_at") or "check time unavailable")
            response += (
                f" The largest free-memory reading on one GPU was {free_mib} MiB "
                f"on {label} GPU {gpu_index} (checked {checked_at}"
                + (f", {utilization}% utilization" if isinstance(utilization, int) else "")
                + "). This is a point-in-time headroom comparison, not a fit guarantee."
            )
            if telemetry.get("status") == "PARTIAL":
                response += " Other configured GPU endpoints could not be read, so the comparison is incomplete."
            return (
                response + " I still can't confirm where a new model will fit: required runtime memory "
                "depends on the model artifact, quantization, context, KV cache, and provider placement."
            )
        if telemetry.get("status") == "PARTIAL":
            response += " GPU telemetry is partial and no linked live device reading was available for comparison."
        return (
            response + " I can't rank a host for another model because live per-host "
            "GPU load and free VRAM aren't connected, and the model's runtime memory "
            "needs (including quantization and context) are unknown. I can't confirm "
            "capacity or fit."
        )

    reachable = []
    all_models = []
    all_loaded = []
    loaded_unknown_labels = set()
    unlinked_labels = set()
    unavailable = 0
    for endpoint in endpoints[:16]:
        if not isinstance(endpoint, dict):
            continue
        endpoint_id = str(endpoint.get("source_identity") or "configured provider")
        machine = resource_names.get(endpoint.get("node_identity"))
        if machine:
            label = str(machine)
        else:
            endpoint_name = endpoint_id.removeprefix("inference:")
            endpoint_name = " ".join(re.sub(r"[._-]+", " ", endpoint_name).split())
            label = (
                f"{endpoint_name.title()} inference endpoint"
                if endpoint_name and endpoint_name != "configured provider"
                else "Configured inference endpoint"
            )
            unlinked_labels.add(label)
        endpoint_status = str(endpoint.get("status") or "UNKNOWN").upper()
        if endpoint_status not in {"READABLE", "PARTIAL"}:
            unavailable += 1
            continue
        reachable.append(label)
        models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
        loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
        all_models.extend((label, model) for model in models if isinstance(model, dict))
        if endpoint.get("loaded_status") == "CURRENT":
            all_loaded.extend((label, model) for model in loaded if isinstance(model, dict))
        elif models:
            loaded_unknown_labels.add(label)

    if ai_availability:
        configured_count = len(endpoints[:16])
        if not reachable:
            return (
                "I couldn't confirm the AI endpoints are responding; none of the configured "
                "provider catalog checks succeeded. I haven't tested a generation."
            )
        if unavailable:
            return (
                f"{len(reachable)} of {configured_count} configured AI provider checks are responding; "
                f"{unavailable} could not be verified. I haven't tested a generation, so I can't "
                "confirm the AI can answer a prompt right now."
            )
        return (
            f"All {len(reachable)} configured AI provider checks are responding to catalog reads. "
            "I haven't tested a generation, so I can't confirm the AI can answer a prompt right now."
        )

    where_match = re.search(
        r"\bwhere(?:['’]s|\s+is)\s+([a-z0-9._-]+(?::[a-z0-9._-]+)?(?:\s+\d+(?:\.\d+)?b)?)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    if where_match:
        requested = where_match.group(1).strip()[:128].casefold()
        matches = [
            (label, model) for label, model in all_models
            if requested in str(model.get("name") or "").casefold()
        ]
        if matches:
            locations = sorted({label for label, _model in matches})
            names = sorted({str(model.get("name")) for _label, model in matches})
            target_names = {name.casefold() for name in names}
            loaded_locations = sorted({
                label for label, model in all_loaded
                if str(model.get("name") or "").casefold() in target_names
            })
            result = f"{', '.join(names[:3])} is listed by {', '.join(locations[:4])}."
            if loaded_locations:
                result += f" Provider reports it resident on {', '.join(loaded_locations[:4])}."
            elif any(label in loaded_unknown_labels for label in locations):
                result += " Current loaded-model state is unavailable for at least one matching provider."
            else:
                result += " It is not currently reported as loaded."
            if any(label in unlinked_labels for label in locations):
                result += " I can't verify which physical machine this endpoint belongs to."
            retrieved_at = str(inventory.get("retrieved_at") or "").strip()
            if retrieved_at:
                result += f" Provider catalog and residency reads completed at {retrieved_at[:80]}."
            else:
                result += " Provider catalog and residency read time is unavailable."
            if unavailable:
                provider_word = "provider" if unavailable == 1 else "providers"
                result += (
                    f" {unavailable} configured inference {provider_word} could not be checked,"
                    " so other model locations may be missing."
                )
            return (
                result
                + " This checks provider catalog and residency APIs; it does not prove GPU execution "
                "or that a generation request succeeds."
            )
        if not reachable:
            return "I can't verify that model right now because no configured provider catalog responded."
        result = f"I couldn't find {requested} in the model catalogs that responded."
        if unavailable:
            result += f" {unavailable} configured provider(s) could not be checked."
        return result

    if not reachable:
        return "I couldn't verify installed or loaded models because no configured provider catalog responded."
    names = list(dict.fromkeys(
        str(model.get("name")) for _label, model in all_models if model.get("name")
    ))[:12]
    loaded_names = list(dict.fromkeys(
        f"{model.get('name')} on {label}" for label, model in all_loaded if model.get("name")
    ))[:8]
    result = f"I checked {len(reachable)} configured model provider(s) just now."
    if names:
        result += " Installed: " + ", ".join(names) + "."
    else:
        result += " No installed models were reported."
    if loaded_names:
        result += " Provider-reported residency: " + ", ".join(loaded_names) + "."
    elif all(endpoint.get("loaded_status") == "CURRENT" for endpoint in endpoints if isinstance(endpoint, dict)):
        result += " No models are currently reported as loaded."
    else:
        result += " Current loaded-model state is partly unavailable."
    if unavailable:
        result += f" I couldn't check {unavailable} other configured provider(s)."
    return (
        result
        + " Catalog and residency reads do not prove GPU execution or a successful generation, "
        "and they do not establish free GPU capacity."
    )
