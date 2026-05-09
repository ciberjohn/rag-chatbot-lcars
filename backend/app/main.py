import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import settings
from .rag.indexer import DocumentIndexer
from .rag.retriever import DocumentRetriever
from .chat.engine import ChatEngine
from .watcher.drive_watcher import start_watcher
from .routes.chat import router as chat_router
from .routes.admin import router as admin_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MyTechBooksWizzard (model=%s)", settings.model)

    indexer = DocumentIndexer()
    retriever = DocumentRetriever(indexer.collection, indexer.embedder)
    engine = ChatEngine(retriever)

    app.state.indexer = indexer
    app.state.retriever = retriever
    app.state.chat_engine = engine

    observer, scheduler = start_watcher(indexer)

    # Run initial index in background so the server comes up immediately
    loop = asyncio.get_running_loop()
    logger.info("Scheduling background document index…")
    loop.run_in_executor(None, indexer.index_all)

    yield

    observer.stop()
    observer.join(timeout=5)
    scheduler.shutdown(wait=False)
    logger.info("Shutdown complete")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MyTechBooksWizzard",
    lifespan=lifespan,
    # Disable public API docs
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    # Restrict to same origin — UI is served by this app so no cross-origin needed
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

app.include_router(chat_router)
app.include_router(admin_router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
