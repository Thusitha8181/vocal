import uuid
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlmodel import col, select

from app.db.models import AccountStatus, Bill, ConnectionType, Customer, Plan, Usage
from app.db.session import session_scope
from app.rag.store import asearch
from app.services import calls
from app.services.phone import normalize_phone

NOT_VERIFIED = (
    "The caller is not verified yet. Ask for their registered Lauki phone number and the "
    "account holder's name, then call verify_customer before sharing any account details."
)


def _call_id(config: RunnableConfig) -> uuid.UUID | None:
    value = (config.get("configurable") or {}).get("call_id")
    return uuid.UUID(str(value)) if value else None


async def _verified_customer(config: RunnableConfig) -> Customer | None:
    call_id = _call_id(config)
    return await calls.get_call_customer(call_id) if call_id else None


def _gb(mb: int) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def _describe_plan(plan: Plan) -> str:
    price = (
        f"{plan.price_inr} rupees per month"
        if plan.connection_type == ConnectionType.postpaid
        else f"{plan.price_inr} rupees for {plan.validity_days} days"
    )
    return (
        f"{plan.name} ({plan.connection_type}), {price}. "
        f"Allowance: {_gb(plan.data_mb)} data, {plan.voice_minutes} minutes, {plan.sms} SMS. "
        f"Benefits: {plan.benefits}"
    )


@tool
async def list_plans() -> str:
    """List every Lauki Phones plan currently on sale, with price, validity, data, minutes,
    SMS and benefits. Use it when the caller asks which plans exist, wants to compare plans
    or asks for a plan's price or allowance."""
    async with session_scope() as session:
        plans = (await session.exec(select(Plan).order_by(col(Plan.price_inr)))).all()
    lines = [f"- {_describe_plan(plan)}" for plan in plans]
    return (
        f"Lauki Phones sells exactly {len(plans)} plans:\n"
        + "\n".join(lines)
        + "\nThe caller has not heard this list. Answer their question from it out loud."
    )


@tool(response_format="content_and_artifact")
async def search_knowledge_base(query: str) -> tuple[str, list[dict[str, Any]]]:
    """Search Lauki Phones' official documents: plans and pricing, billing and payments FAQ,
    late fees, refunds, recharges, plan switching, network coverage, 5G availability and
    signal troubleshooting. Use it for any policy or product question. Pass a focused,
    self-contained search query."""
    chunks = await asearch(query)
    if not chunks:
        return "No relevant information found in the knowledge base.", []
    body = "\n\n---\n\n".join(
        f"[{i}] {c.title} (page {c.page})\n{c.content}" for i, c in enumerate(chunks, start=1)
    )
    return body, [c.as_dict() for c in chunks]


@tool
async def verify_customer(
    phone_number: str, account_holder_name: str, config: RunnableConfig
) -> str:
    """Verify the caller's identity using their registered phone number and the account
    holder's name (first name is enough). Must succeed before any account tool is used."""
    call_id = _call_id(config)
    phone = normalize_phone(phone_number)
    if not phone or call_id is None:
        return "That phone number doesn't look valid. Ask the caller to repeat it digit by digit."

    async with session_scope() as session:
        customer = await calls.find_customer_by_phone(session, phone)
    if customer is None:
        return "No Lauki account is registered to that number. Ask the caller to double-check it."

    spoken = {part for part in account_holder_name.lower().replace(".", " ").split() if part}
    if not spoken & set(customer.full_name.lower().split()):
        return "The name does not match the account on that number. Do not reveal the name on file."

    await calls.attach_customer(call_id, customer)
    return f"Verified. The caller is {customer.full_name}. Greet them by first name."


@tool
async def get_account_overview(config: RunnableConfig) -> str:
    """Get the verified caller's plan, connection type, account status, prepaid validity,
    bill cycle date and autopay setting."""
    customer = await _verified_customer(config)
    if customer is None:
        return NOT_VERIFIED
    async with session_scope() as session:
        plan = await session.get(Plan, customer.plan_code)
    assert plan is not None

    lines = [
        f"Name: {customer.full_name}, city: {customer.city}",
        f"Plan: {_describe_plan(plan)}",
        f"Account status: {customer.account_status}",
    ]
    if customer.account_status == AccountStatus.suspended:
        lines.append("Outgoing services are suspended because of an unpaid bill.")
    if customer.validity_ends_on:
        days = (customer.validity_ends_on - date.today()).days
        when = f"in {days} days" if days >= 0 else f"{-days} days ago"
        lines.append(f"Prepaid validity ends on {customer.validity_ends_on:%d %B %Y} ({when})")
    if customer.bill_cycle_day:
        lines.append(f"Bill is generated on day {customer.bill_cycle_day} of each month")
    lines.append(f"Autopay: {'enabled' if customer.autopay_enabled else 'not enabled'}")
    return "\n".join(lines)


@tool
async def get_latest_bill(config: RunnableConfig) -> str:
    """Get the verified caller's most recent postpaid bill: amount, due date, payment status
    and itemised line items. Use this to explain why a bill is higher than expected."""
    customer = await _verified_customer(config)
    if customer is None:
        return NOT_VERIFIED
    async with session_scope() as session:
        stmt = (
            select(Bill)
            .where(Bill.customer_id == customer.id)
            .order_by(col(Bill.period_start).desc())
            .limit(1)
        )
        bill = (await session.exec(stmt)).first()
    if bill is None:
        return "This customer has no bills. Prepaid customers pay upfront through recharges."

    items = "\n".join(f"- {i['description']}: {i['amount_inr']} rupees" for i in bill.line_items)
    days_to_due = (bill.due_date - date.today()).days
    due = f"due in {days_to_due} days" if days_to_due >= 0 else f"{-days_to_due} days past due"
    paid = f", paid on {bill.paid_on:%d %B %Y}" if bill.paid_on else ""
    return (
        f"Bill period: {bill.period_start:%d %B} to {bill.period_end:%d %B %Y}\n"
        f"Total: {bill.amount_inr} rupees\n"
        f"Due date: {bill.due_date:%d %B %Y} ({due})\n"
        f"Status: {bill.status}{paid}\n"
        f"Line items:\n{items}"
    )


@tool
async def get_usage(config: RunnableConfig) -> str:
    """Get the verified caller's data, voice and SMS usage for the current cycle and what
    remains of their plan allowance, including rolled-over data."""
    customer = await _verified_customer(config)
    if customer is None:
        return NOT_VERIFIED
    async with session_scope() as session:
        plan = await session.get(Plan, customer.plan_code)
        stmt = (
            select(Usage)
            .where(Usage.customer_id == customer.id)
            .order_by(col(Usage.period_start).desc())
            .limit(1)
        )
        usage = (await session.exec(stmt)).first()
    if usage is None or plan is None:
        return "No usage recorded for the current cycle yet."

    data_total = plan.data_mb + usage.rollover_data_mb
    return (
        f"Cycle started: {usage.period_start:%d %B %Y}\n"
        f"Data: used {_gb(usage.data_used_mb)} of {_gb(data_total)} "
        f"(includes {_gb(usage.rollover_data_mb)} rollover), "
        f"{_gb(max(data_total - usage.data_used_mb, 0))} left\n"
        f"Voice: used {usage.voice_used_minutes} of {plan.voice_minutes} minutes\n"
        f"SMS: used {usage.sms_used} of {plan.sms}"
    )


@tool
async def end_call(reason: str, message: str) -> str:
    """End the call once the caller's questions are answered and they say goodbye or confirm
    they need nothing else. `message` is the short farewell spoken before hanging up."""
    return "Call ended."


TOOLS = [
    search_knowledge_base,
    list_plans,
    verify_customer,
    get_account_overview,
    get_latest_bill,
    get_usage,
    end_call,
]
