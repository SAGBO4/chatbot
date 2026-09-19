"""Live crypto market data."""
from fastapi import APIRouter, Depends, HTTPException

from app.observability import get_logger
from app.schemas import CryptoPriceResponse
from app.security import verify_api_key
from app.services.crypto_service import CryptoService

logger = get_logger(__name__)
router = APIRouter(tags=["crypto"])


@router.get(
    "/api/crypto/{symbol}",
    response_model=CryptoPriceResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_crypto_price(symbol: str):
    """Live market data for an asset symbol (e.g. `btc`): 404 for an unknown symbol, 503 when the price provider is down."""
    if CryptoService.resolve_asset_id(symbol) is None:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{symbol}'")

    data = await CryptoService.get_market_data(symbol)
    if data is None:
        raise HTTPException(status_code=503, detail="Crypto market data temporarily unavailable")

    return CryptoPriceResponse(symbol=symbol.lower(), **data)
