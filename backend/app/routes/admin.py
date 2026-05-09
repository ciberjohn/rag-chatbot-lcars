import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..config import settings
from ..models import StatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
_reindex_pool = ThreadPoolExecutor(max_workers=1)


def _verify_admin(x_admin_token: str = Header(default="")):
    expected = settings.admin_token.get_secret_value()
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/status", response_model=StatusResponse)
async def status(request: Request):
    s = request.app.state.indexer.status()
    return StatusResponse(
        total_chunks=s["total_chunks"],
        indexed_files=s["indexed_files"],
        last_sync=s["last_sync"],
        model=settings.model,
    )


@router.post("/reindex")
async def reindex(request: Request):
    indexer = request.app.state.indexer
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_reindex_pool, indexer.index_all)
    return {"message": "Re-index triggered"}
