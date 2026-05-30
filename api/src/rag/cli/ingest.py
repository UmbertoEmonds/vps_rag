"""CLI entry point for local PDF ingestion.

Usage:
    # Mode bucket : liste et ingère depuis GCS
    uv run python -m rag.cli.ingest

    # Mode local : ingère depuis un dossier + upload vers GCS
    uv run python -m rag.cli.ingest --docs-dir path/to/docs/

    # Mode local sans upload
    uv run python -m rag.cli.ingest --docs-dir path/to/docs/ --no-upload

Exit codes:
    0 — always (individual errors are reported and skipped)
"""
from __future__ import annotations

import argparse
import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rag.cli._runner import async_session
from rag.rag.ingestion.pipeline import ingest_pdf
from rag.rag.storage.corpus import get_storage

REMOTE_PREFIX = "docs/"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest PDF files into the vector store"
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        required=False,
        default=None,       # None = mode bucket
        help="Dossier local de PDFs (si absent : liste depuis le bucket GCS)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Ne pas uploader vers le bucket après ingestion locale",
    )
    return parser.parse_args()


@dataclass
class _Summary:
    ingested: int = 0
    skipped: int = 0
    errors: int = 0
    uploaded: int = 0
    files: list = field(default_factory=list)


async def _ingest_from_bucket(storage, summary: _Summary) -> None:
    """Télécharge et ingère tous les PDFs listés dans le bucket."""
    remote_keys = storage.list_pdfs(prefix=REMOTE_PREFIX)
    if not remote_keys:
        print(f"No PDF files found in bucket under prefix '{REMOTE_PREFIX}'")
        return

    print(f"Found {len(remote_keys)} PDF(s) in bucket")

    with tempfile.TemporaryDirectory() as tmpdir:
        async with async_session() as db:
            for key in remote_keys:
                filename = Path(key).name
                local_path = Path(tmpdir) / filename
                try:
                    print(f"  ↓ Downloading: {key}")
                    storage.download(key, local_path)
                    result = await ingest_pdf(local_path, db)
                    if result.already_existed:
                        print(f"  [SKIP]  {filename} — already ingested")
                        summary.skipped += 1
                    else:
                        print(f"  [OK]    {filename} — {result.chunks_created} chunks")
                        summary.ingested += 1
                    summary.files.append(key)
                except Exception as exc:
                    print(f"  [ERROR] {filename} — {exc}")
                    summary.errors += 1


async def _ingest_from_local(
    docs_dir: Path,
    storage,
    upload: bool,
    summary: _Summary,
) -> None:
    """Ingère les PDFs depuis un dossier local, avec upload optionnel."""
    if not docs_dir.exists():
        print(f"Docs directory not found: {docs_dir}")
        return

    pdfs = sorted(docs_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {docs_dir}")
        return

    print(f"Found {len(pdfs)} PDF file(s) in {docs_dir}")

    async with async_session() as db:
        for pdf in pdfs:
            try:
                result = await ingest_pdf(pdf, db)
                if result.already_existed:
                    print(f"[SKIP]  {pdf.name} — already ingested")
                    summary.skipped += 1
                else:
                    print(f"[OK]    {pdf.name} — {result.chunks_created} chunks")
                    summary.ingested += 1

                if upload:
                    remote_key = f"{REMOTE_PREFIX}{pdf.name}"
                    if not storage.exists(remote_key):
                        uri = storage.upload(pdf, remote_key)
                        print(f"  ↑ Uploaded: {uri}")
                        summary.uploaded += 1
                    else:
                        print(f"  → Already in bucket: {remote_key}")

            except Exception as exc:
                print(f"[ERROR] {pdf.name} — {exc}")
                summary.errors += 1


async def _run(docs_dir: Path | None, upload: bool) -> None:
    storage = get_storage()
    summary = _Summary()

    if docs_dir is not None:
        await _ingest_from_local(docs_dir, storage, upload=upload, summary=summary)
    else:
        await _ingest_from_bucket(storage, summary=summary)

    uploaded_msg = f", Uploaded: {summary.uploaded}" if summary.uploaded else ""
    print(
        f"\nDone. Ingested: {summary.ingested}, "
        f"Skipped: {summary.skipped}, "
        f"Errors: {summary.errors}"
        f"{uploaded_msg}"
    )


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.docs_dir, upload=not args.no_upload))


if __name__ == "__main__":
    main()