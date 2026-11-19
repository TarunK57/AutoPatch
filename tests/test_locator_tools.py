"""Unit tests for tool dispatch resilience and error handling."""

from pathlib import Path
import pytest
from autopatch.intelligence.service import CodeIntelligenceService
from autopatch.locator.models import ToolCallRequest
from autopatch.locator.tools import CodeSearchToolDispatcher


@pytest.fixture
def search_dispatcher(tmp_path: Path):
    root = tmp_path / "tools_proj"
    root.mkdir()
    (root / "app.py").write_text("class Server:\n    def start(self):\n        return True\n")

    service = CodeIntelligenceService()
    project_id = "test_tools"
    service.index_project(project_id, root)
    engine = service.get_search_engine(project_id, root)
    return CodeSearchToolDispatcher(engine)


def test_unknown_tool_call_returns_helpful_error_not_crash(search_dispatcher):
    """Acceptance criterion: unknown tool calls must return a helpful error, not crash."""
    req = ToolCallRequest(
        tool="execute_arbitrary_shell_command",
        arguments={"cmd": "ls"},
        reasoning="Attempting unknown tool",
    )
    record = search_dispatcher.execute_call(req, stratum=1)

    assert record.success is False
    assert "Unknown tool 'execute_arbitrary_shell_command'" in record.error_message
    assert "Available search tools:" in record.error_message
    assert "search_class" in record.error_message


def test_missing_required_arguments_returns_error(search_dispatcher):
    """Verify tool execution returns error on missing required parameters."""
    req = ToolCallRequest(
        tool="search_class",
        arguments={},  # Missing class_name
        reasoning="Forgot argument",
    )
    record = search_dispatcher.execute_call(req, stratum=1)

    assert record.success is False
    assert "Missing required parameter 'class_name'" in record.error_message


def test_valid_tool_dispatch(search_dispatcher):
    """Verify standard tool invocation succeeds and builds EvidenceRecord."""
    req = ToolCallRequest(
        tool="search_method",
        arguments={"method_name": "start"},
        reasoning="Locate Server start method",
    )
    record = search_dispatcher.execute_call(req, stratum=1)

    assert record.success is True
    assert record.error_message is None
    assert "Found 1 match" in record.result_summary
    assert record.stratum == 1
