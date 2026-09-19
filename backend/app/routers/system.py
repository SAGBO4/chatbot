"""Health check."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.observability import get_logger
from app.openapi_docs import error_responses
from app.schemas import HealthResponse

logger = get_logger(__name__)
router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses=error_responses({503: "The database does not answer."}),
)
async def health_check(session: AsyncSession = Depends(get_db)):
    """Liveness probe: pings the database and answers 503 if it is unreachable."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "service": "support-bot-backend"}
    except Exception as exc:
        logger.error("Health check database connectivity failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connectivity error",
        )
