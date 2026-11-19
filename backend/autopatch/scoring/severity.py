"""Severity calculation based on category, call-graph reachability, and blast radius."""

from __future__ import annotations

import networkx as nx
from pathlib import Path
from typing import List, Optional, Set, Tuple

from autopatch.core.models import Severity
from autopatch.detection.models import FindingCategory
from autopatch.intelligence.graph import DependencyGraphs
from autopatch.scoring.config import ScoringConfig
from autopatch.scoring.models import BugCategory, ReachabilityStatus, SeverityBreakdown


class SeverityCalculator:
    """Calculates multidimensional defect severity with call-graph reachability analysis."""

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig.load_from_file()

    def map_category(self, raw_category: str, cwe: Optional[str] = None, desc: str = "") -> BugCategory:
        """Maps finding or string category to standardized BugCategory."""
        cat_lower = str(raw_category).lower()
        desc_lower = desc.lower()

        if cwe or "security" in cat_lower or any(k in desc_lower for k in ["sql", "injection", "xss", "secret", "traversal"]):
            return BugCategory.SECURITY
        if "data_loss" in cat_lower or "resource_leak" in cat_lower or "leak" in desc_lower or "corruption" in desc_lower:
            return BugCategory.DATA_LOSS
        if "crash" in cat_lower or "zero_division" in desc_lower or "null" in desc_lower or "none" in desc_lower or "exception" in cat_lower:
            return BugCategory.CRASH
        if "wrong_output" in cat_lower or "logic_error" in cat_lower or "validation" in cat_lower or "off_by_one" in desc_lower or "nan" in desc_lower:
            return BugCategory.WRONG_OUTPUT
        if "style" in cat_lower or "lint" in cat_lower:
            return BugCategory.STYLE

        return BugCategory.WRONG_OUTPUT

    def compute_severity(
        self,
        category: BugCategory,
        file_path: str,
        symbol: Optional[str] = None,
        dependency_graphs: Optional[DependencyGraphs] = None,
        entry_points: Optional[List[str]] = None,
    ) -> SeverityBreakdown:
        """Calculates severity using category weight, entry point reachability, and blast radius."""
        # 1. Base category weight
        cat_weights = self.config.category_weights
        weights_map = {
            BugCategory.SECURITY: cat_weights.security,
            BugCategory.DATA_LOSS: cat_weights.data_loss,
            BugCategory.CRASH: cat_weights.crash,
            BugCategory.WRONG_OUTPUT: cat_weights.wrong_output,
            BugCategory.STYLE: cat_weights.style,
        }
        base_weight = weights_map.get(category, 0.50)

        # 2. Reachability analysis
        reach_status, reach_factor, reach_path = self._evaluate_reachability(
            file_path=file_path,
            symbol=symbol,
            dependency_graphs=dependency_graphs,
            entry_points=entry_points or [],
        )

        # 3. Blast radius analysis (caller count & critical path)
        callers_count = 0
        if dependency_graphs and symbol:
            callers_count = len(dependency_graphs.callers(symbol))

        caller_boost = min(
            self.config.blast_radius.max_caller_boost,
            callers_count * self.config.blast_radius.caller_count_scale,
        )

        is_critical_path, critical_keywords = self._check_critical_path(file_path, symbol)
        crit_multiplier = (
            self.config.blast_radius.critical_path_multiplier if is_critical_path else 1.00
        )

        blast_multiplier = round(crit_multiplier + caller_boost, 4)

        # 4. Final numeric score clamped to [0.0, 1.0]
        raw_score = base_weight * reach_factor * (crit_multiplier * (1.0 + caller_boost))
        numeric_severity = round(min(1.0, max(0.05, raw_score)), 4)

        # 5. Categorical Severity level mapping
        if numeric_severity >= 0.75:
            level = Severity.CRITICAL
        elif numeric_severity >= 0.50:
            level = Severity.HIGH
        elif numeric_severity >= 0.25:
            level = Severity.MEDIUM
        else:
            level = Severity.LOW

        # 6. Explanation
        explanation = (
            f"Severity {level.value} (score {numeric_severity:.2f}). "
            f"Category '{category.value}' base weight={base_weight:.2f}; "
            f"Reachability '{reach_status.value}' (factor={reach_factor:.2f}); "
            f"Blast radius: callers={callers_count} (+{caller_boost:.2f} boost), "
            f"critical_path={is_critical_path} ({', '.join(critical_keywords) if critical_keywords else 'none'})."
        )

        return SeverityBreakdown(
            category=category,
            category_base_weight=base_weight,
            reachability_status=reach_status,
            reachability_factor=reach_factor,
            reachability_path=reach_path,
            callers_count=callers_count,
            is_critical_path=is_critical_path,
            critical_keywords_matched=critical_keywords,
            blast_radius_multiplier=blast_multiplier,
            numeric_severity=numeric_severity,
            severity_level=level,
            explanation=explanation,
        )

    def _evaluate_reachability(
        self,
        file_path: str,
        symbol: Optional[str],
        dependency_graphs: Optional[DependencyGraphs],
        entry_points: List[str],
    ) -> Tuple[ReachabilityStatus, float, List[str]]:
        rw = self.config.reachability_weights

        # If file is itself an entry point
        if any(file_path.endswith(ep) or ep.endswith(file_path) for ep in entry_points):
            return ReachabilityStatus.ENTRY_POINT_DIRECT, rw.entry_point_direct, [file_path]

        if not dependency_graphs or not dependency_graphs.call_graph:
            # Fallback when no AST call graph is available
            is_public = symbol and not symbol.startswith("_")
            if is_public:
                return ReachabilityStatus.PUBLIC_API, rw.public_api, []
            return ReachabilityStatus.INTERNAL_REACHABLE, rw.internal_reachable, []

        cg: nx.DiGraph = dependency_graphs.call_graph

        # Find target nodes matching symbol or file
        target_nodes = []
        target_symbol = symbol or ""
        for node in cg.nodes:
            if target_symbol and (node.endswith(f":{target_symbol}") or node == target_symbol):
                target_nodes.append(node)
            elif not target_symbol and node.startswith(f"{file_path}:"):
                target_nodes.append(node)

        if not target_nodes:
            # Check public naming convention
            if target_symbol and not target_symbol.startswith("_"):
                return ReachabilityStatus.PUBLIC_API, rw.public_api, []
            return ReachabilityStatus.INTERNAL_REACHABLE, rw.internal_reachable, []

        target_node = target_nodes[0]

        # Check reachability from entry points
        entry_nodes = []
        for ep in entry_points:
            for node in cg.nodes:
                if node.startswith(f"{ep}:"):
                    entry_nodes.append(node)

        shortest_path: Optional[List[str]] = None
        for en in entry_nodes:
            if nx.has_path(cg, en, target_node):
                p = nx.shortest_path(cg, en, target_node)
                if shortest_path is None or len(p) < len(shortest_path):
                    shortest_path = p

        if shortest_path:
            if len(shortest_path) <= 2:
                return ReachabilityStatus.ENTRY_POINT_DIRECT, rw.entry_point_direct, shortest_path
            return ReachabilityStatus.ENTRY_POINT_INDIRECT, rw.entry_point_indirect, shortest_path

        # If has callers in the graph, it is internal reachable
        if list(cg.predecessors(target_node)):
            return ReachabilityStatus.INTERNAL_REACHABLE, rw.internal_reachable, []

        # If public API name
        if target_symbol and not target_symbol.startswith("_"):
            return ReachabilityStatus.PUBLIC_API, rw.public_api, []

        return ReachabilityStatus.UNREACHABLE, rw.unreachable, []

    def _check_critical_path(self, file_path: str, symbol: Optional[str]) -> Tuple[bool, List[str]]:
        text_to_check = f"{file_path.lower()} {str(symbol or '').lower()}"
        matched: List[str] = []
        for kw in self.config.blast_radius.critical_path_keywords:
            if kw in text_to_check:
                matched.append(kw)
        return len(matched) > 0, matched
