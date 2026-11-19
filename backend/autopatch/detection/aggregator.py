"""Finding deduplication, merging, and agreement-based confidence aggregation."""

from typing import List, Set
from autopatch.detection.models import Finding, FindingCategory


CATEGORY_PRIORITY = {
    FindingCategory.SECURITY: 1,
    FindingCategory.TEST_FAILURE: 2,
    FindingCategory.LOGIC_ERROR: 3,
    FindingCategory.INPUT_VALIDATION: 4,
    FindingCategory.RESOURCE_LEAK: 5,
    FindingCategory.EXCEPTION_HANDLING: 6,
    FindingCategory.STYLE_LINT: 7,
}


def findings_overlap(f1: Finding, f2: Finding) -> bool:
    """Returns True if two findings refer to the same bug site."""
    if f1.file != f2.file:
        return False

    # Check line overlap
    lines_overlap = max(f1.line_start, f2.line_start) <= min(f1.line_end, f2.line_end)

    # Check same symbol
    same_symbol = (
        f1.symbol is not None
        and f2.symbol is not None
        and f1.symbol == f2.symbol
        and abs(f1.line_start - f2.line_start) <= 5
    )

    return lines_overlap or same_symbol


def merge_finding_cluster(cluster: List[Finding]) -> Finding:
    """Merges a cluster of overlapping findings into a single consolidated Finding."""
    if len(cluster) == 1:
        return cluster[0]

    # Best category by priority
    best_category = min(cluster, key=lambda f: CATEGORY_PRIORITY.get(f.category, 99)).category

    # Best CWE if any
    cwe = next((f.cwe for f in cluster if f.cwe), None)

    # Collect unique detector names and calculate combined agreement confidence
    unique_detectors: Set[str] = set()
    detector_confidences: List[float] = []

    for f in cluster:
        # Split any already-combined detector names
        for det in f.detector.split("+"):
            det_clean = det.strip()
            if det_clean not in unique_detectors:
                unique_detectors.add(det_clean)
                detector_confidences.append(f.raw_confidence)

    # Combined confidence from detector agreement:
    # 1.0 - prod(1.0 - c)
    prob_false = 1.0
    for conf in detector_confidences:
        prob_false *= (1.0 - conf)
    combined_confidence = round(min(0.99, max(max(detector_confidences), 1.0 - prob_false)), 4)

    # Choose clearest evidence (longest or most detailed)
    best_evidence = max(cluster, key=lambda f: len(f.evidence)).evidence

    # Primary symbol
    symbol = next((f.symbol for f in cluster if f.symbol), None)

    # Combined detector string
    detector_str = " + ".join(sorted(list(unique_detectors)))

    # Best description
    best_desc = max(cluster, key=lambda f: len(f.description)).description

    min_line = min(f.line_start for f in cluster)
    max_line = max(f.line_end for f in cluster)

    return Finding(
        file=cluster[0].file,
        line_start=min_line,
        line_end=max_line,
        symbol=symbol,
        category=best_category,
        cwe=cwe,
        evidence=best_evidence,
        detector=detector_str,
        raw_confidence=combined_confidence,
        description=best_desc,
        metadata={
            "agreeing_detectors": sorted(list(unique_detectors)),
            "merged_count": len(cluster),
        },
    )


def deduplicate_and_merge_findings(findings: List[Finding]) -> List[Finding]:
    """Clusters and merges overlapping findings across all detectors."""
    if not findings:
        return []

    # Group by file
    by_file: dict[str, List[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f)

    consolidated: List[Finding] = []

    for file_path, file_findings in by_file.items():
        # Cluster overlapping findings using connected components
        clusters: List[List[Finding]] = []

        for candidate in file_findings:
            matched_clusters = []
            for cluster in clusters:
                if any(findings_overlap(candidate, existing) for existing in cluster):
                    matched_clusters.append(cluster)

            if not matched_clusters:
                clusters.append([candidate])
            elif len(matched_clusters) == 1:
                matched_clusters[0].append(candidate)
            else:
                # Merge multiple clusters connected by candidate
                new_cluster = [candidate]
                for c in matched_clusters:
                    new_cluster.extend(c)
                    clusters.remove(c)
                clusters.append(new_cluster)

        # Merge each cluster
        for cluster in clusters:
            consolidated.append(merge_finding_cluster(cluster))

    # Sort deterministically by file and line
    consolidated.sort(key=lambda f: (f.file, f.line_start, f.line_end))
    return consolidated
