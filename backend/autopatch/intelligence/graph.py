"""Call graph and import graph construction using networkx."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set
import networkx as nx

from autopatch.intelligence.models import FileASTIndex


class DependencyGraphs:
    """Maintains directed call and import graphs for code navigation and impact analysis."""

    def __init__(self) -> None:
        # call_graph: edge (caller -> callee) means caller invokes callee
        self.call_graph: nx.DiGraph = nx.DiGraph()
        # import_graph: edge (file -> imported_module) means file imports imported_module
        self.import_graph: nx.DiGraph = nx.DiGraph()

    def build_from_indices(self, indices: List[FileASTIndex]) -> None:
        """Constructs both import graph and call graph from a collection of FileASTIndex objects."""
        # 1. Build Import Graph
        for idx in indices:
            self.import_graph.add_node(idx.file_path, type="file", language=idx.language)
            for imp in idx.imports:
                target_mod = imp.module
                self.import_graph.add_node(target_mod, type="module")
                self.import_graph.add_edge(
                    idx.file_path,
                    target_mod,
                    names=imp.imported_names,
                    line=imp.line,
                )

        # 2. Build Call Graph
        # Register all known functions and methods as nodes
        known_symbols: Set[str] = set()
        for idx in indices:
            for fn in idx.functions:
                sym = f"{idx.file_path}:{fn.name}"
                short_sym = fn.name
                self.call_graph.add_node(sym, short_name=short_sym, file_path=idx.file_path, type="function")
                known_symbols.add(short_sym)

            for m in idx.methods:
                sym = f"{idx.file_path}:{m.class_name}.{m.name}"
                short_sym = f"{m.class_name}.{m.name}"
                method_short = m.name
                self.call_graph.add_node(sym, short_name=short_sym, file_path=idx.file_path, type="method")
                known_symbols.add(short_sym)
                known_symbols.add(method_short)

        # Regex pattern matching function calls: identifier followed by (
        call_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\(")

        for idx in indices:
            for fn in idx.functions:
                caller_sym = f"{idx.file_path}:{fn.name}"
                matches = call_pattern.findall(fn.implementation)
                for called in matches:
                    called_bare = called.split(".")[-1]
                    # Avoid self recursion edge loops if not intentional
                    if called_bare in known_symbols or called in known_symbols:
                        self.call_graph.add_edge(caller_sym, called)

            for m in idx.methods:
                caller_sym = f"{idx.file_path}:{m.class_name}.{m.name}"
                matches = call_pattern.findall(m.implementation)
                for called in matches:
                    # e.g. self.do_something() -> do_something
                    clean_called = called.replace("self.", "").replace("this.", "")
                    called_bare = clean_called.split(".")[-1]
                    if called_bare in known_symbols or clean_called in known_symbols:
                        self.call_graph.add_edge(caller_sym, clean_called)

    def callers(self, symbol: str) -> List[str]:
        """Finds all symbols that call the given symbol (predecessors in call_graph)."""
        callers_set: Set[str] = set()

        # Check exact node match
        if symbol in self.call_graph:
            callers_set.update(self.call_graph.predecessors(symbol))

        # Check nodes matching short name or suffix
        for node in self.call_graph.nodes:
            if node.endswith(f":{symbol}") or node.endswith(f".{symbol}"):
                callers_set.update(self.call_graph.predecessors(node))

        return sorted(list(callers_set))

    def callees(self, symbol: str) -> List[str]:
        """Finds all symbols that the given symbol calls (successors in call_graph)."""
        callees_set: Set[str] = set()

        if symbol in self.call_graph:
            callees_set.update(self.call_graph.successors(symbol))

        for node in self.call_graph.nodes:
            if node == symbol or node.endswith(f":{symbol}") or node.endswith(f".{symbol}"):
                callees_set.update(self.call_graph.successors(node))

        return sorted(list(callees_set))

    def modules_imported_by(self, file_path: str) -> List[str]:
        """Returns all modules imported by the specified file."""
        if file_path in self.import_graph:
            return sorted(list(self.import_graph.successors(file_path)))
        return []

    def files_importing_module(self, module_name: str) -> List[str]:
        """Returns all files that import the specified module."""
        if module_name in self.import_graph:
            return sorted(list(self.import_graph.predecessors(module_name)))
        return []
