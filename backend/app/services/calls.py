import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Call, CallChannel, CallStatus, CallTurn, Customer
from app.db.session import session_scope
from app.services.events import bus
from app.services.phone import digits_only


async def find_customer_by_phone(session: AsyncSession, phone: str) -> Customer | None:
    digits = digits_only(phone)
    if len(digits) < 9:
        return None
    stmt = select(Customer).where(col(Customer.phone).endswith(digits[-9:]))
    return (await session.exec(stmt)).first()


def serialize_turn(turn: CallTurn) -> dict[str, Any]:
    return turn.model_dump(mode="json")


def serialize_call(call: Call, customer: Customer | None = None) -> dict[str, Any]:
    data = call.model_dump(mode="json", exclude={"transcript", "call_metadata"})
    data["customer_name"] = customer.full_name if customer else None
    return data


async def get_or_create_call(
    conversation_id: str, *, channel: CallChannel, caller_number: str | None
) -> tuple[Call, bool]:
    """Return the call for this conversation and whether it was created by this request."""
    async with session_scope() as session:
        call = (
            await session.exec(select(Call).where(Call.conversation_id == conversation_id))
        ).first()
        if call:
            return call, False

        customer = await find_customer_by_phone(session, caller_number) if caller_number else None
        call = Call(
            conversation_id=conversation_id,
            channel=channel,
            caller_number=caller_number,
            customer_id=customer.id if customer else None,
        )
        session.add(call)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            stmt = select(Call).where(Call.conversation_id == conversation_id)
            return (await session.exec(stmt)).one(), False
        await session.refresh(call)

    bus.publish("call.started", {"call": serialize_call(call, customer)})
    return call, True


async def get_call_customer(call_id: uuid.UUID) -> Customer | None:
    async with session_scope() as session:
        call = await session.get(Call, call_id)
        if not call or not call.customer_id:
            return None
        return await session.get(Customer, call.customer_id)


async def attach_customer(call_id: uuid.UUID, customer: Customer) -> None:
    async with session_scope() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return
        call.customer_id = customer.id
        session.add(call)
        await session.commit()
        await session.refresh(call)
    bus.publish("call.updated", {"call": serialize_call(call, customer)})


async def last_turn(call_id: uuid.UUID) -> CallTurn | None:
    async with session_scope() as session:
        stmt = (
            select(CallTurn)
            .where(CallTurn.call_id == call_id)
            .order_by(col(CallTurn.created_at).desc())
            .limit(1)
        )
        return (await session.exec(stmt)).first()


async def add_turn(
    call_id: uuid.UUID,
    role: str,
    content: str = "",
    *,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
    latency_ms: int | None = None,
) -> CallTurn:
    turn = CallTurn(
        call_id=call_id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_args=tool_args,
        sources=sources,
        latency_ms=latency_ms,
    )
    async with session_scope() as session:
        session.add(turn)
        await session.commit()
        await session.refresh(turn)
    bus.publish("call.turn", {"call_id": str(call_id), "turn": serialize_turn(turn)})
    return turn


async def complete_call(conversation_id: str, data: dict[str, Any]) -> Call:
    """Apply an ElevenLabs post-call webhook payload (`data` object) to the call record."""
    metadata = data.get("metadata") or {}
    analysis = data.get("analysis") or {}
    phone_call = metadata.get("phone_call") or {}
    started = metadata.get("start_time_unix_secs")
    duration = metadata.get("call_duration_secs")

    async with session_scope() as session:
        call = (
            await session.exec(select(Call).where(Call.conversation_id == conversation_id))
        ).first()
        if call is None:
            caller = phone_call.get("external_number")
            call = Call(
                conversation_id=conversation_id,
                channel=CallChannel.phone if caller else CallChannel.web,
                caller_number=caller,
            )
            if caller and (customer := await find_customer_by_phone(session, caller)):
                call.customer_id = customer.id
        if started:
            call.started_at = datetime.fromtimestamp(int(started), UTC)
        if duration is not None:
            call.duration_seconds = int(duration)
            call.ended_at = datetime.fromtimestamp(int(started or 0) + int(duration), UTC)
        call.status = CallStatus.failed if data.get("status") == "failed" else CallStatus.completed
        call.summary = analysis.get("transcript_summary")
        success = analysis.get("call_successful")
        call.successful = None if success in (None, "unknown") else success == "success"
        call.transcript = [
            {
                "role": item.get("role"),
                "message": item.get("message"),
                "time_in_call_secs": item.get("time_in_call_secs"),
            }
            for item in data.get("transcript") or []
        ]
        call.call_metadata = {
            "agent_id": data.get("agent_id"),
            "termination_reason": metadata.get("termination_reason"),
            "cost": metadata.get("cost"),
            "phone_call": phone_call or None,
        }
        session.add(call)
        await session.commit()
        await session.refresh(call)
        customer = await session.get(Customer, call.customer_id) if call.customer_id else None

    bus.publish("call.ended", {"call": serialize_call(call, customer)})
    return call
