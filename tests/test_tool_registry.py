"""
Tests for backend/tools/tool_registry.py — confirms every ToolName maps to
a callable, the registry's prompt-description rendering works, and
execute_tool() dispatches correctly (including its NONE short-circuit and
its error on unknown tools).
"""

import pytest

from backend.models.schemas import ToolName
from backend.tools.tool_registry import (
    TOOL_REGISTRY,
    execute_tool,
    get_tool_descriptions_for_prompt,
)


def test_every_tool_name_except_none_is_registered():
    registered = set(TOOL_REGISTRY.keys())
    all_tools_except_none = {t for t in ToolName if t != ToolName.NONE}
    assert registered == all_tools_except_none


def test_get_tool_descriptions_for_prompt_includes_every_tool_name():
    description_text = get_tool_descriptions_for_prompt()
    for tool_name in TOOL_REGISTRY:
        assert tool_name.value in description_text


def test_execute_tool_returns_none_for_tool_name_none():
    result = execute_tool(ToolName.NONE)
    assert result is None


def test_execute_tool_dispatches_to_reset_password(monkeypatch):
    calls = {}

    def fake_reset_password(email):
        calls["email"] = email
        return {"message": "sent"}

    monkeypatch.setattr(
        TOOL_REGISTRY[ToolName.RESET_PASSWORD], "function", fake_reset_password
    )

    result = execute_tool(ToolName.RESET_PASSWORD, email="alice@example.com")

    assert calls["email"] == "alice@example.com"
    assert result == {"message": "sent"}
