
from __future__ import annotations

import asyncio
from threading import Event, Thread

from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobIngestionResult,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


class JobIngestionExecutorClosed(RuntimeError):
    pass


class ThreadedJobIngestionExecutor:
    """
    Explicit synchronous-to-async integration boundary.

    A dedicated long-lived event loop executes the async authoritative
    ingestion service. Consumer-tool handlers and jobs-faction orchestration
    remain synchronous and do not construct hidden event loops.
    """

    def __init__(
        self,
        service: JobIngestionService,
    ) -> None:
        self._service = service
        self._ready = Event()
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None

        self._thread = Thread(
            target=self._run_loop,
            name="gideon-job-ingestion",
            daemon=True,
        )

        self._thread.start()
        self._ready.wait()

        if self._loop is None:
            raise RuntimeError(
                "Job ingestion event loop failed to initialize."
            )

    def _run_loop(
        self,
    ) -> None:
        loop = asyncio.new_event_loop()

        self._loop = loop

        asyncio.set_event_loop(
            loop
        )

        self._ready.set()

        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(
                loop
            )

            for task in pending:
                task.cancel()

            if pending:
                loop.run_until_complete(
                    asyncio.gather(
                        *pending,
                        return_exceptions=True,
                    )
                )

            loop.close()

    def ingest(
        self,
        candidate: JobIngestionCandidate,
    ) -> JobIngestionResult:
        if self._closed:
            raise JobIngestionExecutorClosed(
                "Job ingestion executor is closed."
            )

        loop = self._loop

        if loop is None:
            raise RuntimeError(
                "Job ingestion event loop is unavailable."
            )

        future = asyncio.run_coroutine_threadsafe(
            self._service.ingest(
                candidate
            ),
            loop,
        )

        return future.result()

    def close(
        self,
    ) -> None:
        if self._closed:
            return

        self._closed = True

        loop = self._loop

        if loop is not None:
            loop.call_soon_threadsafe(
                loop.stop
            )

        self._thread.join(
            timeout=5
        )

        if self._thread.is_alive():
            raise RuntimeError(
                "Job ingestion executor did not stop cleanly."
            )

    def __enter__(
        self,
    ) -> "ThreadedJobIngestionExecutor":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.close()
