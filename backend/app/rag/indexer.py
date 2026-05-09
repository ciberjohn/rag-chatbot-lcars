import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import torch
import chromadb
from chromadb.config import Settings as ChromaSettings
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer
import pypdf

# Limit PyTorch to 2 threads so background indexing doesn't saturate all CPUs
torch.set_num_threads(2)
torch.set_num_interop_threads(1)

from ..config import settings

logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB guard
_HASHES_FILE = "file_hashes.json"


class DocumentIndexer:
    def __init__(self):
        auth_token = settings.chroma_auth_token.get_secret_value()
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            headers=headers,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._lock = threading.Lock()
        self._file_hashes: Dict[str, str] = self._load_hashes()
        self.last_sync: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Hash persistence (survives container restarts)
    # ------------------------------------------------------------------

    def _hashes_path(self) -> Path:
        p = Path(settings.data_path)
        p.mkdir(parents=True, exist_ok=True)
        return p / _HASHES_FILE

    def _load_hashes(self) -> Dict[str, str]:
        path = self._hashes_path()
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception as exc:
                logger.warning("could not load hash cache: %s", exc)
        return {}

    def _save_hashes(self):
        try:
            self._hashes_path().write_text(json.dumps(self._file_hashes))
        except Exception as exc:
            logger.error("could not save hash cache: %s", exc)

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text(self, path: Path) -> str:
        try:
            if path.suffix == ".pdf":
                reader = pypdf.PdfReader(str(path))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            if path.suffix == ".docx":
                doc = DocxDocument(str(path))
                return "\n".join(p.text for p in doc.paragraphs)
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.error("extract failed %s: %s", path, exc)
            return ""

    def _chunk(self, text: str, size: int = 400, overlap: int = 40) -> List[str]:
        words = text.split()
        chunks, i = [], 0
        while i < len(words):
            chunk = " ".join(words[i : i + size])
            if chunk.strip():
                chunks.append(chunk)
            i += size - overlap
        return chunks

    # ------------------------------------------------------------------
    # Index / remove  (all public methods are thread-safe via _lock)
    # ------------------------------------------------------------------

    def index_file(self, path: Path) -> int:
        if path.suffix.lower() not in SUPPORTED:
            return 0
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                logger.warning("skipping oversized file: %s", path)
                return 0
        except FileNotFoundError:
            logger.debug("file disappeared before indexing (rclone temp): %s", path)
            return 0

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        key = str(path)

        with self._lock:
            if self._file_hashes.get(key) == file_hash:
                return 0  # unchanged

            self._remove_chunks_for(path)

            text = self._extract_text(path)
            chunks = self._chunk(text)
            if not chunks:
                return 0

            embeddings = self.embedder.encode(chunks, show_progress_bar=False).tolist()

            # Prefix with a path hash to prevent collisions between same-named files
            path_hash = hashlib.sha256(key.encode()).hexdigest()[:8]
            ids = [f"{path_hash}::{path.name}::c{i}" for i in range(len(chunks))]
            metas = [
                {
                    "filename": path.name,
                    "filepath": key,
                    "chunk_index": i,
                    "file_type": path.suffix.lower(),
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                }
                for i in range(len(chunks))
            ]

            self.collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metas)
            self._file_hashes[key] = file_hash
            self._save_hashes()

        logger.info("indexed %s → %d chunks", path.name, len(chunks))
        return len(chunks)

    def remove_file(self, path: Path):
        with self._lock:
            self._remove_chunks_for(path)
            self._file_hashes.pop(str(path), None)
            self._save_hashes()

    def _remove_chunks_for(self, path: Path):
        try:
            result = self.collection.get(where={"filepath": str(path)})
            if result["ids"]:
                self.collection.delete(ids=result["ids"])
        except Exception as exc:
            logger.error("remove failed %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Full sync
    # ------------------------------------------------------------------

    def index_all(self):
        docs_root = Path(settings.docs_path).resolve()
        if not docs_root.exists():
            logger.warning("docs path missing: %s", docs_root)
            return

        found_paths = set()
        total = 0

        for f in docs_root.rglob("*"):
            if not f.is_file():
                continue
            # Symlink escape check
            try:
                real = f.resolve()
                if not str(real).startswith(str(docs_root)):
                    logger.warning("path escape blocked: %s → %s", f, real)
                    continue
            except Exception:
                continue
            if f.suffix.lower() not in SUPPORTED:
                continue
            found_paths.add(str(f))
            try:
                total += self.index_file(f)
            except Exception as exc:
                logger.error("index error %s: %s", f, exc)
            time.sleep(0.5)  # yield CPU between files so the API stays responsive

        # Remove chunks for files that no longer exist
        with self._lock:
            stale = [p for p in list(self._file_hashes) if p not in found_paths]
        for p in stale:
            logger.info("removing stale file: %s", p)
            self.remove_file(Path(p))

        self.last_sync = datetime.now(timezone.utc)
        logger.info("full index done: %d new/updated chunks, %d stale removed", total, len(stale))

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            files = [Path(p).name for p in self._file_hashes.keys()]
        return {
            "total_chunks": self.collection.count(),
            "indexed_files": files,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
        }
