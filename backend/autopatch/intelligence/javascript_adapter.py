"""Tree-sitter AST LanguageAdapter for JavaScript and TypeScript."""

from pathlib import Path
from typing import List, Optional
import tree_sitter_javascript as tsjs
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


class JavaScriptAdapter(LanguageAdapter):
    """Parses JavaScript and TypeScript source files using tree-sitter."""

    def __init__(self) -> None:
        self._language = Language(tsjs.language())
        self._parser = Parser(self._language)

    @property
    def language_name(self) -> str:
        return "JavaScript"

    @property
    def supported_extensions(self) -> List[str]:
        return [".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"]

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

        def process_node(node: Node) -> None:
            # Handle export default / export wrappers
            if node.type in {"export_statement", "export_default_declaration"}:
                for child in node.children:
                    if child.type in {"class_declaration", "function_declaration", "lexical_declaration"}:
                        process_node(child)
                return

            if node.type == "import_statement":
                # import { a, b } from "module"; or import foo from "module";
                module_name = ""
                imported_names: List[str] = []
                source_node = node.child_by_field_name("source")
                if source_node:
                    module_name = get_text(source_node).strip("\"'")

                clause = node.child_by_field_name("clause") or node
                for child in clause.children:
                    if child.type == "identifier":
                        imported_names.append(get_text(child))
                    elif child.type == "named_imports":
                        for spec in child.children:
                            if spec.type == "import_specifier":
                                name_child = spec.child_by_field_name("name") or spec
                                imported_names.append(get_text(name_child))

                imports.append(
                    ImportDefinition(
                        file_path=rel_path,
                        module=module_name or "unknown",
                        imported_names=imported_names,
                        line=node.start_point.row + 1,
                    )
                )

            elif node.type == "function_declaration":
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
                    )
                )

            elif node.type in {"lexical_declaration", "variable_declaration"}:
                # Handle const fn = () => {} or let fn = function() {}
                for decl in node.children:
                    if decl.type == "variable_declarator":
                        name_node = decl.child_by_field_name("name")
                        val_node = decl.child_by_field_name("value")
                        if name_node and val_node and val_node.type in {"arrow_function", "function", "function_expression"}:
                            fn_name = get_text(name_node)
                            body_node = val_node.child_by_field_name("body")
                            sig_end = body_node.start_byte if body_node else val_node.end_byte
                            signature = f"const {fn_name} = " + code_bytes[val_node.start_byte : sig_end].decode("utf-8", errors="replace").strip()
                            functions.append(
                                FunctionDefinition(
                                    name=fn_name,
                                    file_path=rel_path,
                                    signature=signature,
                                    implementation=get_text(node),
                                    range=get_range(node),
                                )
                            )

            elif node.type in {"interface_declaration", "type_alias_declaration"}:
                # TypeScript interface or type alias
                name_node = node.child_by_field_name("name")
                if name_node:
                    classes.append(
                        ClassDefinition(
                            name=get_text(name_node),
                            file_path=rel_path,
                            signature=get_text(node).split("{")[0].strip(),
                            range=get_range(node),
                        )
                    )

            elif node.type == "class_declaration":
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
                    )
                )

                if body_node:
                    for item in body_node.children:
                        if item.type == "method_definition":
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
                                )
                            )

        for top_node in tree.root_node.children:
            process_node(top_node)

        return FileASTIndex(
            file_path=rel_path,
            language="JavaScript",
            classes=classes,
            functions=functions,
            methods=methods,
            imports=imports,
        )
