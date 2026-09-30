#!/usr/bin/env python3
"""Keep Hermes-generated metadata prompts out of HADES user-action routes."""
from __future__ import annotations

import ast
import re
from pathlib import Path

source = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
guard = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "_HADES_HERMES_AUXILIARY_PROMPT" for target in node.targets)
)
helper = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_is_hermes_auxiliary_prompt"
)
run = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
)
assert isinstance(run.body[0], ast.If), "auxiliary guard must run before capability/action routing"
assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_original_run_conversation"
    for node in ast.walk(run.body[0])
), "auxiliary prompt must delegate to Hermes without HADES action routing"
namespace = {"re": re}
exec(compile(ast.Module(body=[guard, helper], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
is_auxiliary = namespace["_hades_is_hermes_auxiliary_prompt"]
for prompt in (
    "### Task:\nGenerate a concise title summarizing the chat history.",
    "### Task:\nSuggest 3-5 relevant follow-up questions or prompts for the user.",
    "### Task:\nGenerate 1-3 broad tags categorizing the conversation.",
):
    assert is_auxiliary(prompt), prompt
for prompt in (
    "Do we have milk?",
    "Add milk to the shopping list.",
    "Tell me why my shopping list changed.",
):
    assert not is_auxiliary(prompt), prompt
print("PASS Hermes metadata prompts bypass HADES capability and mutation routes")
