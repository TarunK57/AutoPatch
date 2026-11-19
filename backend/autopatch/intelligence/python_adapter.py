"""Tree-sitter AST LanguageAdapter for Python."""

from pathlib import Path
from typing import List, Optional
import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from autopatch.intelligence.adapter import LanguageAdapter
from autopatch.intelligence.models import (
    ClassDefinition,
    FileASTIndex,
    FunctionDefinition,
    ImportDefinition,
    MethodDefinition,
    SourceRange,
)


class PythonAdapter(LanguageAdapter):
    """Parses Python source files using tree-sitter."""

    def __init__(self) -> None:
        self._language = Language(tspython.language())
        self._parser = Parser(self._language)

    @property
    def language_name(self) -> str:
        return "Python"

    @property
    def supported_extensions(self) -> List[str]:
        return [".py"]

    def parse_file(self, rel_path: str, source_code: str) -> FileASTIndex:
        code_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(code_bytes)

        classes: List[ClassDefinition] = []
        functions: List[FunctionDefinition] = []
        methods: List[MethodDefinition] = []
        imports: List[ImportDefinition] = []

        def get_text(node: Node) -> str:
            return code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def get_range(node: Node) -> SourceRange:
            return SourceRange(
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                start_col=node.start_point.column,
                end_col=node.end_point.column,
            )

        def extract_docstring(body_node: Optional[Node]) -> Optional[str]:
            if not body_node:
                return None
            for child in body_node.children:
                if child.type == "expression_statement":
                    first_child = child.children[0] if child.children else None
                    if first_child and first_child.type == "string":
                        doc = get_text(first_child).strip("\"'")
                        return doc
                elif child.type not in {"comment", "newline"}:
                    break
            return None

        for node in tree.root_node.children:
            # Module-level imports: import os, sys
            if node.type == "import_statement":
                imported_names: List[str] = []
                for child in node.children:
                    if child.type in {"dotted_name", "aliased_import"}:
                        imported_names.append(get_text(child))
                imports.append(
                    ImportDefinition(
                        file_path=rel_path,
                        module=imported_names[0] if imported_names else "unknown",
                        imported_names=imported_names,
                        line=node.start_point.row + 1,
                    )
                )

            # from module import name1, name2
            elif node.type == "import_from_statement":
                mod_node = node.child_by_field_name("module_name")
                module_name = get_text(mod_node) if mod_node else ""

                imported_names: List[str] = []
                after_import = False
                for child in node.children:
                    if child.type == "import":
                        after_import = True
                        continue
                    if after_import:
                        if child.type in {"dotted_name", "identifier", "wildcard_import"}:
                            imported_names.append(get_text(child))
                        elif child.type == "aliased_import":
                            orig = child.child_by_field_name("name")
                            imported_names.append(get_text(orig) if orig else get_text(child))

                imports.append(
                    ImportDefinition(
                        file_path=rel_path,
                        module=module_name or "unknown",
                        imported_names=imported_names,
                        line=node.start_point.row + 1,
                    )
                )

            # Module-level function definition
            elif node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                body_node = node.child_by_field_name("body")
                fn_name = get_text(name_node) if name_node else "anonymous"

                sig_end = body_node.start_byte if body_node else node.end_byte
                signature = code_bytes[node.start_byte : sig_end].decode("utf-8", errors="replace").strip()

                functions.append(
                    FunctionDefinition(
                        name=fn_name,
                        file_path=rel_path,
                        signature=signature,
                        implementation=get_text(node),
                        range=get_range(node),
                        docstring=extract_docstring(body_node),
                    )
                )

            # Class definition
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                body_node = node.child_by_field_name("body")
                cls_name = get_text(name_node) if name_node else "anonymous"

                sig_end = body_node.start_byte if body_node else node.end_byte
                cls_sig = code_bytes[node.start_byte : sig_end].decode("utf-8", errors="replace").strip()

                classes.append(
                    ClassDefinition(
                        name=cls_name,
                        file_path=rel_path,
                        signature=cls_sig,
                        range=get_range(node),
                        docstring=extract_docstring(body_node),
                    )
                )

                # Inspect methods inside class body
                if body_node:
                    for item in body_node.children:
                        if item.type == "function_definition":
                            m_name_node = item.child_by_field_name("name")
                            m_body_node = item.child_by_field_name("body")
                            m_name = get_text(m_name_node) if m_name_node else "anonymous"

                            m_sig_end = m_body_node.start_byte if m_body_node else item.end_byte
                            m_sig = code_bytes[item.start_byte : m_sig_end].decode("utf-8", errors="replace").strip()

                            methods.append(
                                MethodDefinition(
                                    name=m_name,
                                    class_name=cls_name,
                                    file_path=rel_path,
                                    signature=m_sig,
                                    implementation=get_text(item),
                                    range=get_range(item),
                                    docstring=extract_docstring(m_body_node),
                                )
                            )

        return FileASTIndex(
            file_path=rel_path,
            language="Python",
            classes=classes,
            functions=functions,
            methods=methods,
            imports=imports,
        )
