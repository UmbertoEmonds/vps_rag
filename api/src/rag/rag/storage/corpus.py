from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from google.cloud import storage as gcs


def _make_client() -> gcs.Client:
    """Crée un client GCS, réel ou pointé vers Fake GCS selon l'environnement."""
    endpoint = os.environ.get("STORAGE_GCS_ENDPOINT_URL")
    if endpoint:
        # Dev local : on pointe vers fake-gcs-server
        from google.api_core.client_options import ClientOptions
        from google.auth.credentials import AnonymousCredentials  # <--- ADD THIS
        
        return gcs.Client(
            project=os.environ.get("STORAGE_GCS_PROJECT", "local-dev"),
            client_options=ClientOptions(api_endpoint=endpoint),
            credentials=AnonymousCredentials(),  # <--- ADD THIS (Bypasses authentication)
        )
    # Prod : authentification via GOOGLE_APPLICATION_CREDENTIALS
    return gcs.Client()


@lru_cache(maxsize=1)
def _get_bucket() -> gcs.Bucket:
    client = _make_client()
    bucket_name = os.environ["STORAGE_BUCKET"]
    bucket = client.bucket(bucket_name)

    # En dev, le bucket n'existe peut-être pas encore : on le crée
    if not bucket.exists():
        bucket = client.create_bucket(bucket_name)

    return bucket


class CorpusStorage:
    """Accès au corpus PDF via GCS (réel ou fake)."""

    def upload(self, local_path: Path, remote_key: str) -> str:
        """Upload un fichier local et retourne son URI GCS."""
        bucket = _get_bucket()
        blob = bucket.blob(remote_key)
        blob.upload_from_filename(str(local_path))
        return f"gs://{bucket.name}/{remote_key}"

    def download(self, remote_key: str, local_path: Path) -> None:
        """Télécharge un objet GCS vers le disque local."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob = _get_bucket().blob(remote_key)
        blob.download_to_filename(str(local_path))

    def list_pdfs(self, prefix: str = "docs/") -> list[str]:
        """Liste les clés des PDFs sous un préfixe donné."""
        bucket = _get_bucket()
        return [
            b.name
            for b in bucket.client.list_blobs(bucket.name, prefix=prefix)
            if b.name.endswith(".pdf")
        ]

    def exists(self, remote_key: str) -> bool:
        """Vérifie si un objet existe dans le bucket."""
        return _get_bucket().blob(remote_key).exists()


@lru_cache(maxsize=1)
def get_storage() -> CorpusStorage:
    """Retourne l'instance partagée de CorpusStorage."""
    return CorpusStorage()