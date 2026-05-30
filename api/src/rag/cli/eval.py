"""CLI entry point for RAG evaluation.

Usage:
    uv run python -m rag.cli.eval
    uv run python -m rag.cli.eval --samples path/to/samples.json

Exit codes:
    0 — success
    1 — samples file missing or empty
    2 — runtime error (DB, LLM, etc.)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from rag.cli._runner import async_session
from rag.evaluation.ragas_pipeline import EvaluationSample, run_evaluation

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SAMPLES_PATH = _PROJECT_ROOT / "data" / "evaluation" / "samples.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ragas evaluation")
    parser.add_argument(
        "--samples",
        type=Path,
        default=DEFAULT_SAMPLES_PATH,
        help=f"Path to samples JSON file (default: {DEFAULT_SAMPLES_PATH})",
    )
    return parser.parse_args()


def _load_samples(path: Path) -> list[EvaluationSample]:
    if not path.exists():
        print(f"Samples file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    if not data:
        print(f"Samples file is empty: {path}", file=sys.stderr)
        sys.exit(1)
    return [EvaluationSample(question=s["question"], ground_truth=s["ground_truth"]) for s in data]


async def _run(samples_path: Path) -> None:
    samples = _load_samples(samples_path)
    print(f"Running evaluation on {len(samples)} samples...")

    async with async_session() as db:
        result = await run_evaluation(samples, db)

    print(
        f"faithfulness={result.faithfulness or 0.0:.3f}  "
        f"answer_relevancy={result.answer_relevancy or 0.0:.3f}  "
        f"context_recall={result.context_recall or 0.0:.3f}"
    )


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_run(args.samples))
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
