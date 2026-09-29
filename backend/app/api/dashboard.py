import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.models import Bill, Call, CallTurn, Customer, Plan, Usage
from app.db.session import get_session
from app.services.calls import serialize_call, serialize_turn
from app.services.events import bus, to_json

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=1)
    total = (await session.exec(select(func.count()).select_from(Call))).one()
    today = (
        await session.exec(select(func.count()).select_from(Call).where(Call.started_at >= since))
    ).one()
    verified = (
        await session.exec(
            select(func.count()).select_from(Call).where(col(Call.customer_id).is_not(None))
        )
    ).one()
    avg_duration = (await session.exec(select(func.avg(Call.duration_seconds)))).one()
    avg_latency = (
        await session.exec(
            select(func.avg(CallTurn.latency_ms)).where(CallTurn.role == "assistant")
        )
    ).one()
    tool_usage = (
        await session.exec(
            select(CallTurn.tool_name, func.count())
            .where(CallTurn.role == "tool")
            .group_by(CallTurn.tool_name)
        )
    ).all()
    return {
        "total_calls": total,
        "calls_last_24h": today,
        "verified_rate": round(verified / total, 3) if total else 0,
        "avg_duration_seconds": round(float(avg_duration), 1) if avg_duration else None,
        "avg_first_token_ms": round(float(avg_latency)) if avg_latency else None,
        "tool_usage": {name: count for name, count in tool_usage if name},
    }


@router.get("/calls")
async def list_calls(
    limit: int = 50, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    stmt = (
        select(Call, Customer)
        .join(Customer, col(Call.customer_id) == col(Customer.id), isouter=True)
        .order_by(col(Call.started_at).desc())
        .limit(min(limit, 200))
    )
    turn_counts = dict(
        (
            await session.exec(select(CallTurn.call_id, func.count()).group_by(CallTurn.call_id))
        ).all()
    )
    rows = (await session.exec(stmt)).all()
    return [
        serialize_call(call, customer) | {"turn_count": turn_counts.get(call.id, 0)}
        for call, customer in rows
    ]


@router.get("/calls/{call_id}")
async def get_call(call_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    customer = await session.get(Customer, call.customer_id) if call.customer_id else None
    turns = (
        await session.exec(
            select(CallTurn).where(CallTurn.call_id == call_id).order_by(col(CallTurn.created_at))
        )
    ).all()
    return serialize_call(call, customer) | {
        "transcript": call.transcript,
        "call_metadata": call.call_metadata,
        "turns": [serialize_turn(t) for t in turns],
    }


@router.get("/customers")
async def list_customers(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    customers = (await session.exec(select(Customer).order_by(Customer.full_name))).all()
    plans = {p.code: p for p in (await session.exec(select(Plan))).all()}
    latest_bills: dict[uuid.UUID, Bill] = {}
    for bill in (await session.exec(select(Bill).order_by(col(Bill.period_start)))).all():
        latest_bills[bill.customer_id] = bill
    usage = {u.customer_id: u for u in (await session.exec(select(Usage))).all()}

    result = []
    for c in customers:
        plan, bill, use = plans.get(c.plan_code), latest_bills.get(c.id), usage.get(c.id)
        result.append(
            c.model_dump(mode="json")
            | {
                "plan": plan.model_dump(mode="json") if plan else None,
                "latest_bill": bill.model_dump(mode="json") if bill else None,
                "usage": use.model_dump(mode="json") if use else None,
            }
        )
    return result


@router.get("/events")
async def events(request: Request) -> EventSourceResponse:
    async def stream():
        async for event in bus.subscribe():
            if await request.is_disconnected():
                break
            yield {"event": event["type"], "data": to_json(event)}

    return EventSourceResponse(stream(), ping=15)
