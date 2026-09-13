"""HADES runtime compatibility overlay for Hermes' Hindsight provider.

The upstream Hindsight plugin exposes an agentic reflection tool alongside
direct retain/recall. Local Ollama models can recurse through reflection after
retrieval instead of returning the owner-facing answer. Keep the supported
provider intact, but expose only the direct memory tools to the HADES profile.
"""

import re


def _hades_subject_from_session_key(session_key):
    """Extract the server-generated subject from an Open WebUI key.

    Open WebUI can expand ``{{USER_ID}}`` in a connection header. Hermes'
    API gateway already accepts that header as a stable session key, so this
    small translation lets the supported Hindsight provider resolve its
    ``{user}`` bank template without trusting model text or a mutable display
    name. Unrecognized keys intentionally produce no subject.
    """
    prefix = "hades-user-"
    if not isinstance(session_key, str) or not session_key.startswith(prefix):
        return ""
    subject = session_key[len(prefix):].strip()
    if not subject or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", subject):
        return ""
    return subject


try:
    import json
    import logging
    import threading
    from plugins.memory import hindsight as _hindsight
    from hindsight_client.hindsight_client import Hindsight as _HindsightClient
    import cli as _hermes_cli
    from agent.web_search_registry import register_provider as _register_web_provider
    from plugins.web.searxng.provider import SearXNGWebSearchProvider
    _hades_logger = logging.getLogger("hades.overlay")
    _hades_memory_local = threading.local()

    # The profile plugin is discovered lazily, while the legacy web tool
    # resolves its backend on first use. Register the packaged provider at
    # interpreter startup so resolution cannot race plugin discovery.
    _register_web_provider(SearXNGWebSearchProvider())

    _hades_original_handle_tool_call = _hindsight.HindsightMemoryProvider.handle_tool_call

    # Hindsight's retain endpoint supports background processing.  The
    # provider's default client call waits for local LLM fact extraction,
    # which can exceed the owner-facing chat timeout when Ollama is sharing
    # the GPU with Hermes.  Submit writes asynchronously; recall remains
    # synchronous so answers never use an unverified write as truth.
    _hades_original_aretain = _HindsightClient.aretain
    _hades_original_aretain_batch = _HindsightClient.aretain_batch

    async def _hades_aretain(self, *args, **kwargs):
        kwargs["retain_async"] = True
        return await _hades_original_aretain(self, *args, **kwargs)

    async def _hades_aretain_batch(self, *args, **kwargs):
        kwargs["retain_async"] = True
        return await _hades_original_aretain_batch(self, *args, **kwargs)

    _HindsightClient.aretain = _hades_aretain
    _HindsightClient.aretain_batch = _hades_aretain_batch

    def _hades_prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall the current query before the model's first API call.

        Hermes' stock Hindsight prefetch is queued at turn end, which makes
        the first turn of a new owner session unable to use relevant memory.
        HADES uses the direct recall endpoint here so the current query gets
        its context synchronously; reflection remains intentionally disabled.
        """
        if self._memory_mode == "tools" or not self._auto_recall or not query.strip():
            return ""
        if self._recall_max_input_chars and len(query) > self._recall_max_input_chars:
            query = query[:self._recall_max_input_chars]
        recall_kwargs = {
            "bank_id": self._bank_id,
            "query": query,
            "budget": self._budget,
            "max_tokens": self._recall_max_tokens,
        }
        if self._recall_tags:
            recall_kwargs["tags"] = self._recall_tags
            recall_kwargs["tags_match"] = self._recall_tags_match
        if self._recall_types:
            recall_kwargs["types"] = self._recall_types
        try:
            response = self._run_hindsight_operation(
                lambda client: client.arecall(**recall_kwargs)
            )
            seen = set()
            lines = []
            for item in (response.results or []):
                text = " ".join(str(item.text or "").split())
                if not text:
                    continue
                # Hindsight can return several retained paraphrases of the
                # same fact. Keep the first occurrence, but don't let those
                # duplicates crowd out a more specific result.
                key = text.split(" | ", 1)[0].casefold()
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {text}")
            if not lines:
                return ""
            header = self._recall_prompt_preamble or (
                "# Hindsight Memory (persistent cross-session context)\n"
                "Use this to answer questions about the user and prior sessions. "
                "Prefer a specific matching fact (such as a named location, "
                "version, or preference) over a generic description. "
                "Do not call tools to look up information already present here."
            )
            return header + "\n\n" + "\n".join(lines)
        except Exception:
            return ""

    def _hades_memory_tools(self):
        if self._memory_mode == "context":
            return []
        return [_hindsight.RETAIN_SCHEMA, _hindsight.RECALL_SCHEMA]

    def _hades_handle_tool_call(self, tool_name, args, **kwargs):
        result = _hades_original_handle_tool_call(self, tool_name, args, **kwargs)
        if tool_name == "hindsight_retain" and isinstance(result, str):
            try:
                payload = json.loads(result)
                if payload.get("result") == "Memory stored successfully.":
                    payload["result"] = "Memory accepted for background storage."
                    return json.dumps(payload)
            except Exception:
                pass
        if tool_name != "hindsight_recall" or not isinstance(result, str):
            return result
        try:
            payload = json.loads(result)
            raw = payload.get("result")
            if not isinstance(raw, str) or not raw.strip() or raw.startswith("No relevant"):
                return result
            facts = [line.strip() for line in raw.splitlines() if line.strip()]
            seen = set()
            unique = []
            for fact in facts:
                text = re.sub(r"^\d+\.\s*", "", fact).strip()
                key = text.split(" | ", 1)[0].casefold()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(text)

            def specificity(text):
                concrete = len(re.findall(
                    r"\b(?:node|host|server|location|version|port|model|address|running on|located|prefer|favorite)\b",
                    text,
                    re.IGNORECASE,
                ))
                identifiers = len(re.findall(r"\b[A-Z0-9][A-Za-z0-9_.:/-]{2,}\b", text))
                return (concrete, identifiers, len(text))

            unique.sort(key=specificity, reverse=True)
            payload["result"] = "\n".join(f"{i}. {fact}" for i, fact in enumerate(unique, 1))
            _hades_memory_local.result = payload["result"]
            return json.dumps(payload)
        except Exception:
            return result

    # Keep automatic context disabled for now: broad Hindsight recall can
    # surface low-confidence acceptance fixtures on unrelated prompts. The
    # direct hindsight_recall tool remains available for explicit memory work.
    _hindsight.HindsightMemoryProvider.get_tool_schemas = _hades_memory_tools
    _hindsight.HindsightMemoryProvider.handle_tool_call = _hades_handle_tool_call

    # Local Ollama routing policy: keep conversational turns on the quick
    # 14B model, but move turns that plainly require an external/current
    # source or durable memory to the local model that reliably emits tool
    # calls.  This is intentionally a small deployment overlay rather than a
    # second HADES router; Hermes still owns the turn lifecycle and tools.
    _hades_original_resolve_turn = _hermes_cli.HermesCLI._resolve_turn_agent_config
    _HADES_TOOL_INTENT = re.compile(
        r"\b(?:remember(?:ed|ing)?|recall|forget|did i tell|do you remember|memory|"
        r"weather|forecast|temperature|search|look up|latest|news|web|"
        r"grocery|groceries|shopping list|recipe|food|pantry|inventory|"
        r"what(?:'s| is) running|what(?:'s| is) down|homelab|server|proxmox|"
        r"netbox|uptime|docker|finance|finances|spending|spent|subscription|"
        r"bank|account balance|before payday)\b",
        re.IGNORECASE,
    )
    # The OpenAI-compatible API server constructs AIAgent directly rather
    # than going through HermesCLI's turn resolver.  Route at the agent turn
    # boundary instead; profile/runtime initialization has completed by this
    # point, so this cannot erase the selected provider or model.
    from run_agent import AIAgent as _AIAgent

    # The API gateway can construct agents after MCP discovery but before the
    # dynamic server alias is visible to its platform allowlist. Reconcile
    # HADES-owned MCP toolsets at the agent boundary so owner-facing API turns
    # receive the same schemas as an explicit toolset run.
    _hades_original_agent_init = _AIAgent.__init__

    def _hades_agent_init(self, *args, **kwargs):
        session_key = kwargs.get("gateway_session_key")
        subject = _hades_subject_from_session_key(session_key)
        if subject and not kwargs.get("user_id"):
            kwargs["user_id"] = subject
            _hades_logger.info("API subject propagated to agent user_id")
        _hades_original_agent_init(self, *args, **kwargs)
        tools = getattr(self, "tools", None)
        if not isinstance(tools, list):
            return
        from model_tools import get_tool_definitions as _get_tool_definitions
        existing = {
            t.get("function", {}).get("name") for t in tools
        }
        extra = []
        if not any(name.startswith("mcp_grocy_") for name in existing):
            extra.extend(_get_tool_definitions(
                enabled_toolsets=["mcp-grocy"], quiet_mode=True
            ))
        # Finance is deliberately not reconciled here.  It is a privileged,
        # owner-only capability and must be explicitly enabled by a future
        # capability boundary; a user message must never grant access to it.
        added_count = 0
        for tool in extra:
            name = tool.get("function", {}).get("name")
            if name and name not in existing:
                tools.append(tool)
                existing.add(name)
                added_count += 1
        self.valid_tool_names = existing
        _hades_logger.warning(
            "API tool reconciliation added %d HADES MCP tools",
            added_count,
        )

    _AIAgent.__init__ = _hades_agent_init

    _hades_original_run_conversation = _AIAgent.run_conversation

    def _hades_run_conversation(self, user_message, *args, **kwargs):
        original_model = getattr(self, "model", "")
        # Open WebUI sends follow-ups as separate turns.  Domain intent must
        # include the active conversation, otherwise a natural correction such
        # as "remove it" loses the Grocy route and can be misread as an
        # unrelated task-list request by a small local model.
        _hades_history = kwargs.get("conversation_history")
        if not isinstance(_hades_history, list):
            _hades_history = next(
                (value for value in args if isinstance(value, list)), []
            )
        _hades_context_parts = [str(user_message or "")]
        for _hades_message in _hades_history[-8:]:
            if isinstance(_hades_message, dict):
                _hades_content = _hades_message.get("content", "")
                if isinstance(_hades_content, str):
                    _hades_context_parts.append(_hades_content)
        _hades_intent_text = "\n".join(_hades_context_parts)[-12000:]
        memory_intent = re.search(
            r"\b(?:remember(?:ed|ing)?|recall|forget|did i tell|do you remember|memory)\b",
            str(user_message or ""),
            re.IGNORECASE,
        )
        original_stream_callback = getattr(self, "stream_delta_callback", None)
        original_internal_stream_callback = getattr(self, "_stream_callback", None)
        original_tools = getattr(self, "tools", None)
        original_valid_tool_names = getattr(self, "valid_tool_names", None)
        completion_only_model = bool(re.search(
            r"\b(?:dolphin(?:-llama3|3)?|heretic|uncensored|abliterated)\b",
            original_model,
            re.IGNORECASE,
        ))
        grocy_intent = re.search(
            r"\b(?:grocery|groceries|shopping list|recipe|food|pantry|inventory|"
            r"what(?:'s| is) in stock|do we have)\b",
            _hades_intent_text,
            re.IGNORECASE,
        )
        agent_zero_intent = re.search(
            r"\b(?:agent zero|agent0|bounded operator|delegate|delegation)\b",
            _hades_intent_text,
            re.IGNORECASE,
        )
        if grocy_intent and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                grocy_tools = _get_tool_definitions(
                    enabled_toolsets=["mcp-grocy"], quiet_mode=True
                )
                if grocy_tools:
                    self.tools = grocy_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in grocy_tools
                    }
                    _hades_logger.warning(
                        "API Grocy intent narrowed tool catalog to %d tools",
                        len(grocy_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API Grocy intent narrowing failed: %s", exc)
        # Do not expose finance tools based on intent.  Natural-language
        # intent is not authorization; finance remains unavailable until a
        # server-side owner capability is wired into this boundary.
        if agent_zero_intent and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                operator_tools = _get_tool_definitions(
                    enabled_toolsets=["hades-agent-zero"], quiet_mode=True
                )
                if operator_tools:
                    self.tools = operator_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in operator_tools
                    }
                    _hades_logger.warning(
                        "API Agent Zero intent narrowed tool catalog to %d tools",
                        len(operator_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API Agent Zero intent narrowing failed: %s", exc)
        if isinstance(original_tools, list) and not any(
            t.get("function", {}).get("name", "").startswith("mcp_grocy_")
            for t in original_tools
        ):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                extra_grocy = _get_tool_definitions(
                    enabled_toolsets=["mcp-grocy"], quiet_mode=True
                )
                names = {t.get("function", {}).get("name") for t in original_tools}
                for tool in extra_grocy:
                    name = tool.get("function", {}).get("name")
                    if name and name not in names:
                        original_tools.append(tool)
                        names.add(name)
                self.valid_tool_names = names
                _hades_logger.warning(
                    "API turn reconciliation added %d Grocy tools",
                    sum(1 for t in extra_grocy if t.get("function", {}).get("name", "").startswith("mcp_grocy_")),
                )
            except Exception as exc:
                _hades_logger.warning("API turn Grocy reconciliation failed: %s", exc)
        # Open WebUI uses the streaming API.  If a weak local model emits a
        # misleading post-tool continuation, let the authoritative Hindsight
        # result replace it before the API adapter sends any text delta.
        # Tool-progress events remain available while the turn runs.
        # Buffer explicit memory turns while the agent works.  The upstream
        # SSE writer forwards callback deltas but does not read the returned
        # final_response, so emit the authoritative result through the saved
        # callback once the tool loop is complete.
        suppress_stream = bool(
            memory_intent and not grocy_intent and original_stream_callback
        )
        if suppress_stream:
            self.stream_delta_callback = None
            self._stream_callback = None
        # A memory question must not expose unrelated mutation tools to a
        # small local model. Keep the provider's direct memory schemas, but
        # enforce the same boundary in the agent's executable tool set for
        # both streaming and non-streaming callers.
        if memory_intent and isinstance(original_tools, list):
            allowed_memory = {"hindsight_recall", "hindsight_retain"}
            if grocy_intent:
                # Mixed memory/domain requests are especially difficult for
                # small local models when the whole household catalog is
                # visible. Keep only the read tools needed by this turn;
                # mutations remain available on explicit household turns.
                if re.search(r"\b(?:recipe|make|missing|ingredient)\b", _hades_intent_text, re.IGNORECASE):
                    allowed_grocy = {
                        "mcp_grocy_stock_overview_tool",
                        "mcp_grocy_recipe_fulfillment_tool",
                    }
                else:
                    allowed_grocy = {"mcp_grocy_stock_overview_tool"}
                allowed_memory.update(
                    tool.get("function", {}).get("name")
                    for tool in original_tools
                    if tool.get("function", {}).get("name") in allowed_grocy
                )
            self.tools = [
                tool for tool in original_tools
                if tool.get("function", {}).get("name") in allowed_memory
            ]
            self.valid_tool_names = {
                tool["function"]["name"] for tool in self.tools
            }
        # Completion-only creative models are deliberately isolated from the
        # HADES tool catalog, even when the upstream model advertises native
        # function calling. They remain useful for morally grey writing and
        # roleplay without access to memory, Grocy, web, Agent Zero, or hosts.
        if completion_only_model:
            self.tools = []
            self.valid_tool_names = set()
        _hades_memory_local.result = None
        runtime_provider = str(getattr(self, "provider", "") or "").lower()
        runtime_base = str(getattr(self, "base_url", "") or "").lower()
        routed = (
            runtime_provider == "custom"
            and ("11434" in runtime_base or "ollama" in runtime_base)
            and _HADES_TOOL_INTENT.search(str(user_message or ""))
            and original_model == "qwen3:14b"
        )
        if routed:
            self.model = "qwen3:8b"
        try:
            result = _hades_original_run_conversation(self, user_message, *args, **kwargs)
            if memory_intent and not grocy_intent and isinstance(result, dict):
                _hades_logger.warning(
                    "memory turn returned roles=%s final_len=%d",
                    [m.get("role") for m in result.get("messages", []) if isinstance(m, dict)],
                    len(str(result.get("final_response") or "")),
                )
                # Some local tool-capable models emit an unrelated continuation
                # after a successful tool call.  For explicit memory requests,
                # the Hindsight payload is authoritative; preserve it as the
                # owner-facing answer instead of allowing that continuation to
                # fabricate a result.
                memory_result = None
                for message in reversed((result or {}).get("messages", [])):
                    if message.get("role") != "tool":
                        continue
                    try:
                        raw_content = message.get("content", "")
                        if isinstance(raw_content, list):
                            raw_content = " ".join(
                                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                                for part in raw_content
                            )
                        payload = json.loads(str(raw_content))
                        candidate = payload.get("result")
                        if isinstance(candidate, str) and candidate.strip() and not candidate.startswith("No relevant"):
                            memory_result = candidate.strip()
                            break
                    except Exception:
                        continue
                if not memory_result:
                    memory_result = getattr(_hades_memory_local, "result", None)
                if memory_result:
                    result["final_response"] = memory_result
                    _hades_logger.warning(
                        "memory turn authoritative result selected len=%d",
                        len(memory_result),
                    )
                    if suppress_stream:
                        original_stream_callback(memory_result)
                    for message in reversed(result.get("messages", [])):
                        if message.get("role") == "assistant" and not message.get("tool_calls"):
                            message["content"] = memory_result
                            break
            return result
        finally:
            if suppress_stream:
                self.stream_delta_callback = original_stream_callback
                self._stream_callback = original_internal_stream_callback
            if memory_intent:
                self.tools = original_tools
                self.valid_tool_names = original_valid_tool_names
            elif completion_only_model:
                self.tools = original_tools
                self.valid_tool_names = original_valid_tool_names
            if routed:
                self.model = original_model

    _AIAgent.run_conversation = _hades_run_conversation

    def _hades_resolve_turn(self, user_message: str):
        route = _hades_original_resolve_turn(self, user_message)
        # Only route the configured local Ollama profile.  A future remote or
        # provider-specific profile should retain Hermes' native behavior.
        provider = str(route.get("runtime", {}).get("provider") or "").lower()
        base_url = str(route.get("runtime", {}).get("base_url") or "").lower()
        if (
            provider == "custom"
            and ("11434" in base_url or "ollama" in base_url)
            and _HADES_TOOL_INTENT.search(str(user_message or ""))
            and route.get("model") == "qwen3:14b"
        ):
            route["model"] = "qwen3:8b"
            route["signature"] = (
                route["model"],
                route["runtime"]["provider"],
                route["runtime"]["base_url"],
                route["runtime"]["api_mode"],
                route["runtime"]["command"],
                tuple(route["runtime"]["args"]),
            )
        return route

    _hermes_cli.HermesCLI._resolve_turn_agent_config = _hades_resolve_turn

except Exception:
    # Hermes can still start if the optional provider is unavailable; its
    # normal provider diagnostics should report that condition.
    pass
