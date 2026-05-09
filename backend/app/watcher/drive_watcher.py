import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import settings
from ..rag.indexer import DocumentIndexer

logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


class _Handler(FileSystemEventHandler):
    def __init__(self, indexer: DocumentIndexer):
        self.indexer = indexer

    def _ok(self, path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED

    def on_created(self, event):
        if not event.is_directory and self._ok(event.src_path):
            logger.info("new file: %s", event.src_path)
            self.indexer.index_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory and self._ok(event.src_path):
            logger.info("modified: %s", event.src_path)
            self.indexer.index_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and self._ok(event.src_path):
            logger.info("deleted: %s", event.src_path)
            self.indexer.remove_file(Path(event.src_path))


def start_watcher(indexer: DocumentIndexer):
    observer = Observer()
    observer.schedule(_Handler(indexer), settings.docs_path, recursive=True)
    observer.start()
    logger.info("watching %s", settings.docs_path)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        indexer.index_all,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="full_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduled full re-sync every %d min", settings.sync_interval_minutes)

    return observer, scheduler
