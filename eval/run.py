#!/usr/bin/env python3
"""Single executable command to run the AutoPatch evaluation benchmark and generate report.md & results.json."""

import argparse
import sys
from pathlib import Path

# Ensure project root and backend are in python path
root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from eval.runner import run_evaluation_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AutoPatch Benchmark Evaluation Harness: Runs 30 seeded bugs + SWE-bench instances with ablations and generates report.md & results.json."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic reproducibility (default: 42)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of repeated runs for confidence interval calculation (default: 3)",
    )
    parser.add_argument(
        "--swe-bench",
        type=str,
        default=None,
        help="Optional path to SWE-bench Lite JSON/JSONL dataset file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval",
        help="Output directory for report.md and results.json (default: 'eval')",
    )
    parser.add_argument(
        "--no-ablations",
        action="store_true",
        help="Skip running ablation conditions (Full, No-BRT, No-SBFL, Templates, LLM)",
    )

    args = parser.parse_args()

    swe_file = Path(args.swe_bench) if args.swe_bench else None
    out_dir = Path(args.output)

    print("=================================================================")
    print("        AUTOPATCH BENCHMARK EVALUATION HARNESS                   ")
    print("=================================================================")
    print(f"Seed:               {args.seed}")
    print(f"Repeats:            {args.runs}")
    print(f"SWE-bench File:     {swe_file or 'None (using 30 Seeded Bugs across Python & JS)'}")
    print(f"Output Directory:   {out_dir}")
    print(f"Include Ablations:  {not args.no_ablations}")
    print("=================================================================\n")

    res = run_evaluation_benchmark(
        swe_bench_file=swe_file,
        output_dir=out_dir,
        seed=args.seed,
        runs=args.runs,
        include_ablations=not args.no_ablations,
    )

    print("\n-----------------------------------------------------------------")
    print("                 BENCHMARK COMPLETED SUCCESSFULLY                ")
    print("-----------------------------------------------------------------")
    print(f"Total Instances Evaluated: {res['total_instances']}")
    print(f"Markdown Report:           {res['report_markdown']}")
    print(f"Structured Results JSON:   {res['results_json']}")
    print("-----------------------------------------------------------------")

    return 0


if __name__ == "__main__":
    sys.exit(main())
