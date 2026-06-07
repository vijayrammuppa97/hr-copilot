"""
Watches data/knowledge_docs/ for file changes and auto-reindexes the knowledge base.

Uses watchdog if installed, otherwise polls every 30 seconds.
Install watchdog: pip install watchdog
"""

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("hr_copilot.watcher")

DOCS_FOLDER = Path(__file__).parent.parent / "data" / "knowledge_docs"
SUPPORTED   = {".pdf", ".docx", ".csv", ".txt", ".md", ".text"}


class DocumentWatcher:
    def __init__(self, knowledge_base) -> None:  # type: ignore[type-arg]
        self._kb      = knowledge_base
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        DOCS_FOLDER.mkdir(parents=True, exist_ok=True)
        self._running = True
        try:
            self._start_watchdog()
        except ImportError:
            logger.warning("watchdog not installed — using 30-second polling. pip install watchdog for real-time updates.")
            self._start_polling()

    def stop(self) -> None:
        self._running = False

    # ── Watchdog (real-time, preferred) ──────────────────────────────────── #

    def _start_watchdog(self) -> None:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileSystemEvent

        kb = self._kb

        class Handler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:
                self._handle(Path(str(event.src_path)))

            def on_modified(self, event: FileSystemEvent) -> None:
                self._handle(Path(str(event.src_path)))

            def _handle(self, path: Path) -> None:
                if not path.is_file():
                    return
                if path.suffix.lower() not in SUPPORTED:
                    return
                logger.info("File changed — re-indexing: %s", path.name)
                try:
                    kb.reload_file(path)
                    logger.info("Re-indexed %s (total sections=%d)", path.name, kb.section_count)
                except Exception as exc:
                    logger.error("Re-index failed for %s: %s", path.name, exc)

        observer = Observer()
        observer.schedule(Handler(), str(DOCS_FOLDER), recursive=False)
        observer.start()
        logger.info("Watchdog watching %s", DOCS_FOLDER)

    # ── Polling fallback ──────────────────────────────────────────────────── #

    def _start_polling(self) -> None:
        def _poll() -> None:
            mtimes: dict[str, float] = {}
            while self._running:
                try:
                    for path in DOCS_FOLDER.iterdir():
                        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
                            continue
                        mtime = path.stat().st_mtime
                        if mtimes.get(path.name) != mtime:
                            action = "changed" if path.name in mtimes else "added"
                            logger.info("File %s — re-indexing: %s", action, path.name)
                            self._kb.reload_file(path)
                            mtimes[path.name] = mtime
                except Exception as exc:
                    logger.error("Watcher poll error: %s", exc)
                time.sleep(30)

        self._thread = threading.Thread(target=_poll, daemon=True, name="doc-watcher")
        self._thread.start()
        logger.info("Polling watcher started (30s interval) for %s", DOCS_FOLDER)
