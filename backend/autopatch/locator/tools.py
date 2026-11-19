"""Tool execution dispatch for the Locator Agent.

Executes code-search tools against the local AST index and CodeSearchEngine.
Enforces non-crashing resilience: invalid arguments or unknown tools return helpful errors.
"""

from typing import Any, Dict, List, Optional
from autopatch.intelligence.code_search import CodeSearchEngine
from autopatch.intelligence.models import SearchResult
from autopatch.locator.models import EvidenceRecord, ToolCallRequest
from autopatch.security.prompt_defense import ToolCallSecurityValidator

AVAILABLE_TOOLS: List[str] = [
    "search_class",
    "search_class_in_file",
    "search_method",
    "search_method_in_class",
    "search_method_in_file",
    "search_code",
    "search_code_in_file",
]


class CodeSearchToolDispatcher:
    """Safely executes code search tools requested by the Locator Agent."""

    def __init__(self, search_engine: CodeSearchEngine):
        self.search_engine = search_engine

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns tool schema definitions for LLM prompting."""
        return [
            {
                "name": "search_class",
                "description": "Searches for a class by name across all files. Returns class declaration signature only.",
                "parameters": {"class_name": {"type": "string", "required": True}},
            },
            {
                "name": "search_class_in_file",
                "description": "Searches for a class by name within a specific file. Returns signature only.",
                "parameters": {
                    "class_name": {"type": "string", "required": True},
                    "file_path": {"type": "string", "required": True},
                },
            },
            {
                "name": "search_method",
                "description": "Searches for a method or function by name across all files. Returns full implementation.",
                "parameters": {"method_name": {"type": "string", "required": True}},
            },
            {
                "name": "search_method_in_class",
                "description": "Searches for a method inside a specific class. Returns full implementation.",
                "parameters": {
                    "method_name": {"type": "string", "required": True},
                    "class_name": {"type": "string", "required": True},
                },
            },
            {
                "name": "search_method_in_file",
                "description": "Searches for a method inside a specific file. Returns full implementation.",
                "parameters": {
                    "method_name": {"type": "string", "required": True},
                    "file_path": {"type": "string", "required": True},
                },
            },
            {
                "name": "search_code",
                "description": "Searches for a raw code snippet across the project. Returns matching line with +/-3 lines context.",
                "parameters": {"snippet": {"type": "string", "required": True}},
            },
            {
                "name": "search_code_in_file",
                "description": "Searches for a code snippet within a specific file. Returns matching line with +/-3 lines context.",
                "parameters": {
                    "snippet": {"type": "string", "required": True},
                    "file_path": {"type": "string", "required": True},
                },
            },
        ]

    def execute_call(self, request: ToolCallRequest, stratum: int) -> EvidenceRecord:
        """Executes a single tool call request and returns an EvidenceRecord."""
        tool_name = request.tool.strip()
        args = request.arguments or {}

        # 1. Unknown tool handling
        if tool_name not in AVAILABLE_TOOLS:
            avail_str = ", ".join(AVAILABLE_TOOLS)
            err_msg = f"Unknown tool '{tool_name}'. Available search tools: {avail_str}."
            return EvidenceRecord(
                stratum=stratum,
                tool_name=tool_name,
                arguments=args,
                result_summary="Error: Tool not found",
                raw_result={"error": err_msg},
                success=False,
                error_message=err_msg,
            )

        # 1.1 Security validation of arguments
        is_safe, sec_err, cleaned_args = ToolCallSecurityValidator.validate_tool_call(tool_name, args)
        if not is_safe:
            return EvidenceRecord(
                stratum=stratum,
                tool_name=tool_name,
                arguments=args,
                result_summary="Security Violation: Argument rejected",
                raw_result={"error": sec_err},
                success=False,
                error_message=sec_err,
            )
        args = cleaned_args


        try:
            # 2. Dispatch to specific tool with parameter validation
            if tool_name == "search_class":
                cls_name = args.get("class_name") or args.get("cls") or args.get("name")
                if not cls_name:
                    return self._missing_arg_record(tool_name, "class_name", args, stratum)
                results = self.search_engine.search_class(cls_name)
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_class_in_file":
                cls_name = args.get("class_name") or args.get("cls")
                file_path = args.get("file_path") or args.get("f") or args.get("file")
                if not cls_name or not file_path:
                    missing = "class_name" if not cls_name else "file_path"
                    return self._missing_arg_record(tool_name, missing, args, stratum)
                res = self.search_engine.search_class_in_file(cls_name, file_path)
                results = [res] if res else []
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_method":
                m_name = args.get("method_name") or args.get("m") or args.get("name")
                if not m_name:
                    return self._missing_arg_record(tool_name, "method_name", args, stratum)
                results = self.search_engine.search_method(m_name)
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_method_in_class":
                m_name = args.get("method_name") or args.get("m")
                cls_name = args.get("class_name") or args.get("cls")
                if not m_name or not cls_name:
                    missing = "method_name" if not m_name else "class_name"
                    return self._missing_arg_record(tool_name, missing, args, stratum)
                results = self.search_engine.search_method_in_class(m_name, cls_name)
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_method_in_file":
                m_name = args.get("method_name") or args.get("m")
                file_path = args.get("file_path") or args.get("f") or args.get("file")
                if not m_name or not file_path:
                    missing = "method_name" if not m_name else "file_path"
                    return self._missing_arg_record(tool_name, missing, args, stratum)
                results = self.search_engine.search_method_in_file(m_name, file_path)
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_code":
                snippet = args.get("snippet") or args.get("code")
                if not snippet:
                    return self._missing_arg_record(tool_name, "snippet", args, stratum)
                results = self.search_engine.search_code(snippet)
                return self._build_record(stratum, tool_name, args, results)

            elif tool_name == "search_code_in_file":
                snippet = args.get("snippet") or args.get("code")
                file_path = args.get("file_path") or args.get("f") or args.get("file")
                if not snippet or not file_path:
                    missing = "snippet" if not snippet else "file_path"
                    return self._missing_arg_record(tool_name, missing, args, stratum)
                results = self.search_engine.search_code_in_file(snippet, file_path)
                return self._build_record(stratum, tool_name, args, results)

            else:
                return self._missing_arg_record(tool_name, "unknown", args, stratum)

        except Exception as e:
            return EvidenceRecord(
                stratum=stratum,
                tool_name=tool_name,
                arguments=args,
                result_summary=f"Execution error: {str(e)}",
                raw_result={"error": str(e)},
                success=False,
                error_message=str(e),
            )

    def _missing_arg_record(
        self, tool_name: str, missing_arg: str, args: Dict[str, Any], stratum: int
    ) -> EvidenceRecord:
        err = f"Missing required parameter '{missing_arg}' for tool '{tool_name}'."
        return EvidenceRecord(
            stratum=stratum,
            tool_name=tool_name,
            arguments=args,
            result_summary=f"Error: {err}",
            raw_result={"error": err},
            success=False,
            error_message=err,
        )

    def _build_record(
        self, stratum: int, tool_name: str, args: Dict[str, Any], results: List[SearchResult]
    ) -> EvidenceRecord:
        count = len(results)
        if count == 0:
            summary = "No matches found."
        elif count == 1:
            summary = f"Found 1 match in {results[0].file_path} (lines {results[0].line_start}-{results[0].line_end})"
        else:
            files = sorted(list(set(r.file_path for r in results)))
            summary = f"Found {count} matches across {len(files)} file(s): {', '.join(files[:3])}"

        return EvidenceRecord(
            stratum=stratum,
            tool_name=tool_name,
            arguments=args,
            result_summary=summary,
            raw_result=[r.model_dump() for r in results],
            success=True,
            error_message=None,
        )
