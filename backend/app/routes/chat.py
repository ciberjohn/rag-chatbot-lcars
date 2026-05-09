import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    engine = request.app.state.chat_engine
    try:
        return await engine.chat(
            message=body.message,
            history=body.history,
            use_web_search=body.use_web_search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error. Check server logs.")
