"""Portfolio routes — current state, trade execution, value history."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import repo
from app.services.portfolio import execute_trade, get_portfolio

router = APIRouter(prefix="/api/portfolio")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


@router.get("")
async def portfolio() -> dict:
    return get_portfolio()


@router.post("/trade")
async def trade(req: TradeRequest) -> dict:
    result = await execute_trade(req.ticker, req.side, req.quantity)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/history")
async def history() -> dict:
    snapshots = [
        {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
        for s in repo.list_snapshots()
    ]
    return {"snapshots": snapshots}
