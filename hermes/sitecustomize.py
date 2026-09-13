"""HADES runtime compatibility overlay for Hermes' Hindsight provider.

The upstream Hindsight plugin exposes an agentic reflection tool alongside
direct retain/recall. Local Ollama models can recurse through reflection after
retrieval instead of returning the owner-facing answer. Keep the supported
provider intact, but expose only the direct memory tools to the HADES profile.
"""

import os
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


def _hades_session_scope(session_key):
    """Return the server-selected capability scope for a gateway session."""
    if not isinstance(session_key, str):
        return ""
    if session_key.startswith("hades-user-"):
        # Open WebUI uses one server-expanded template for all authenticated
        # users. Resolve the owner exception from a private service setting,
        # never from model text or a client-provided role/group claim.
        subject = _hades_subject_from_session_key(session_key)
        if not subject:
            # A prefix alone is not authentication. Invalid or empty subjects
            # must remain denied rather than inheriting household capability.
            return ""
        owner_subject = os.environ.get("HADES_OWNER_SUBJECT_ID", "").strip()
        if subject == owner_subject:
            return "owner"
        return "household"
    # Do not honor a client-selectable owner prefix. Production Open WebUI
    # emits only the server-expanded hades-user template, and unknown session
    # formats must fail closed.
    return ""


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

    _hades_original_sync_turn = _hindsight.HindsightMemoryProvider.sync_turn
    _HADES_SHARED_MEMORY_INTENT = re.compile(
        r"\b(?:grocy|grocery|groceries|grocry|grocerys|shopping list|pantry|inventory|stock|"
        r"recipe|food|ingredient|bought|purchase|purchased|consume|"
        r"consumed|used up|out of|add it|remove it)\b",
        re.IGNORECASE,
    )
    _HADES_GROCY_ACTION_INTENT = re.compile(
        r"\b(?:add|remove|buy|bought|purchase|consume|used|out of|outta)\s+"
        r"(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|"
        r"pasta|rice|chicken|beef|fruit|vegetables?)\b",
        re.IGNORECASE,
    )
    _HADES_GROCY_ITEM_FRAGMENT = re.compile(
        r"^\s*(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|"
        r"beef|fruit|vegetables?)\s*[?!.,]*\s*$",
        re.IGNORECASE,
    )
    _HADES_EXPLICIT_MEMORY_INTENT = re.compile(
        r"\b(?:remember|memorize|forget|memory|recall|do you remember|"
        r"actually my|correction)\b",
        re.IGNORECASE,
    )

    def _hades_sync_turn(self, user_content, assistant_content, *, session_id=""):
        """Keep shared household turns out of private semantic memory.

        Grocy is the canonical household store. Hermes' generic automatic
        retain path otherwise persists the entire completed turn, including
        live shopping-list/tool results, into the authenticated user's private
        Hindsight bank. Explicit memory requests remain eligible for retain;
        ordinary shared-state turns do not become personal memory by accident.
        """
        # Classify from the user's request only. Assistant/tool output is
        # untrusted generated text and must not decide whether a turn is
        # private or shared.
        user_text = str(user_content or "")
        if (
            (
                _HADES_SHARED_MEMORY_INTENT.search(user_text)
                or _HADES_GROCY_ACTION_INTENT.search(user_text)
                or _HADES_GROCY_ITEM_FRAGMENT.search(user_text)
            )
            and not _HADES_EXPLICIT_MEMORY_INTENT.search(user_text)
        ):
            _hades_logger.info("Skipping automatic Hindsight retain for shared-state turn")
            return None
        return _hades_original_sync_turn(
            self, user_content, assistant_content, session_id=session_id
        )

    _hindsight.HindsightMemoryProvider.sync_turn = _hades_sync_turn

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
        # Grocy is authoritative for live household state. Do not inject
        # stale personal semantic-memory claims into a live Grocy question,
        # especially when Grocy is unavailable and the model must report a
        # dependency failure. Explicit memory requests may still compose with
        # a Grocy read.
        if (
            (
                _HADES_SHARED_MEMORY_INTENT.search(query)
                or _HADES_GROCY_ACTION_INTENT.search(query)
                or _HADES_GROCY_ITEM_FRAGMENT.search(query)
            )
            and not _HADES_EXPLICIT_MEMORY_INTENT.search(query)
        ):
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
        r"grocy|grocery|groceries|grocry|grocerys|shopping list|recipe|food|pantry|inventory|"
        r"what(?:'s| is) running|what(?:'s| is) down|homelab|server|proxmox|"
        r"netbox|uptime|docker|finance|finances|spending|spent|subscription|"
        r"bank|account balance|before payday|"
        r"(?:add|out\s+of|outta)\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|"
        r"pasta|rice|chicken|beef|fruit|vegetables?)|"
        r"remove\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|"
        r"pasta|rice|chicken|beef|fruit|vegetables?))\b|"
        r"^\s*(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|"
        r"beef|fruit|vegetables?)\s*[?!.,]*\s*$",
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
        self._hades_session_scope = _hades_session_scope(session_key)
        if subject and not kwargs.get("user_id"):
            kwargs["user_id"] = subject
            _hades_logger.info("API subject propagated to agent user_id")
        _hades_original_agent_init(self, *args, **kwargs)
        # The profile's private Hindsight JSON is the authoritative runtime
        # config and contains the owner's legacy bank as its static fallback.
        # Override only the provider instance after trusted gateway identity
        # is known: preserve that existing bank for the owner, isolate every
        # household subject, and never fall back to the owner bank when the
        # request has no validated subject.
        memory_scope = getattr(self, "_hades_session_scope", "")
        if self._memory_manager and self._memory_manager.providers:
            if memory_scope == "owner":
                memory_bank = "hades-owner"
            elif memory_scope == "household" and subject:
                memory_bank = f"hades-user-{subject}"
            else:
                memory_bank = "hades-denied"
            for memory_provider in self._memory_manager.providers:
                if hasattr(memory_provider, "_bank_id"):
                    memory_provider._bank_id = memory_bank
                if hasattr(memory_provider, "_auto_recall"):
                    # The profile intentionally disables global auto-recall;
                    # once a trusted subject has selected an isolated bank,
                    # enable scoped prefetch so UI recall does not depend on
                    # a small model choosing the memory tool correctly.
                    memory_provider._auto_recall = memory_scope in {
                        "owner", "household"
                    }
                if memory_scope in {"owner", "household"}:
                    # Bind HADES' synchronous current-query prefetch helper;
                    # the upstream tools-only mode otherwise suppresses
                    # prefetch and makes recall depend on model tool choice.
                    memory_provider._memory_mode = "hybrid"
                    memory_provider.prefetch = _hades_prefetch.__get__(
                        memory_provider, type(memory_provider)
                    )
            _hades_logger.info(
                "Hindsight bank selected from trusted scope: scope=%s subject_present=%s",
                memory_scope or "denied", bool(subject),
            )
        tools = getattr(self, "tools", None)
        if not isinstance(tools, list):
            return
        if self._hades_session_scope == "household":
            # Capability exclusion must happen before model invocation. The
            # base profile may advertise privileged toolsets globally, so do
            # not rely on a later prompt/intent guard to hide them.
            privileged_markers = ("agent_zero", "agent-zero", "finance")
            self.tools = [
                tool for tool in tools
                if not any(
                    marker in str(tool.get("function", {}).get("name", "")).lower()
                    for marker in privileged_markers
                )
            ]
            self.valid_tool_names = {
                tool.get("function", {}).get("name") for tool in self.tools
            }
            tools = self.tools
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
            r"\b(?:grocy|grocery|groceries|grocry|grocerys|shopping list|recipe|food|pantry|inventory|"
            r"what(?:'s| is) in stock|do we have)\b",
            _hades_intent_text,
            re.IGNORECASE,
        ) or _HADES_GROCY_ACTION_INTENT.search(_hades_intent_text)
        if not grocy_intent and _HADES_GROCY_ITEM_FRAGMENT.search(str(user_message or "")):
            grocy_intent = True
        web_intent = re.search(
            r"\b(?:weather|forecast|temperature|search|look up|latest|news|web)\b",
            _hades_intent_text,
            re.IGNORECASE,
        )
        # Conversation history can contain the word "memory" even when the
        # current request is an ordinary Grocy mutation. Disable automatic
        # personal-memory prefetch for that turn at the agent boundary; the
        # explicit-memory path remains available for intentional composition.
        _hades_saved_auto_recall = []
        if grocy_intent and not memory_intent and self._memory_manager:
            for _hades_provider in self._memory_manager.providers:
                if hasattr(_hades_provider, "_auto_recall"):
                    _hades_saved_auto_recall.append(
                        (_hades_provider, _hades_provider._auto_recall)
                    )
                    _hades_provider._auto_recall = False
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
        # The API tool-search catalog can defer web_search even when a
        # keyless SearXNG provider is configured. Small local models may then
        # incorrectly route the deferred tool through tool_call. For an
        # unambiguous web turn, expose the supported web tools directly so
        # the model can emit a normal function call. Mixed household turns
        # retain the Grocy/memory routing above.
        if web_intent and not grocy_intent and not memory_intent and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                web_tools = _get_tool_definitions(
                    enabled_toolsets=["web"], quiet_mode=True
                )
                if web_tools:
                    self.tools = web_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in web_tools
                    }
                    _hades_logger.warning(
                        "API web intent narrowed tool catalog to %d tools",
                        len(web_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API web intent narrowing failed: %s", exc)
        # Do not expose finance tools based on intent.  Natural-language
        # intent is not authorization; finance remains unavailable until a
        # server-side owner capability is wired into this boundary.
        # Household sessions must not gain the bounded operator from prompt
        # wording. The unmarked legacy owner session remains compatible until
        # Open WebUI is configured to send the server-generated scope marker.
        household_session = getattr(self, "_hades_session_scope", "") == "household"
        if agent_zero_intent and not household_session and isinstance(original_tools, list):
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
            for _hades_provider, _hades_auto_recall in _hades_saved_auto_recall:
                _hades_provider._auto_recall = _hades_auto_recall
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
