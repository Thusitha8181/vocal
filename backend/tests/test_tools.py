import uuid

from app.agent.tools import (
    NOT_VERIFIED,
    get_account_overview,
    get_latest_bill,
    get_usage,
    verify_customer,
)
from app.db.models import CallChannel
from app.services import calls


async def _new_call() -> dict:
    call, _ = await calls.get_or_create_call(
        f"test-{uuid.uuid4()}", channel=CallChannel.web, caller_number=None
    )
    return {"configurable": {"call_id": str(call.id)}}


async def test_account_tools_require_verification():
    config = await _new_call()
    assert await get_latest_bill.ainvoke({}, config) == NOT_VERIFIED
    assert await get_usage.ainvoke({}, config) == NOT_VERIFIED


async def test_verify_rejects_wrong_name():
    config = await _new_call()
    result = await verify_customer.ainvoke(
        {"phone_number": "98765 43210", "account_holder_name": "Rahul"}, config
    )
    assert "does not match" in result
    assert await get_account_overview.ainvoke({}, config) == NOT_VERIFIED


async def test_verified_caller_gets_bill_and_usage():
    config = await _new_call()
    result = await verify_customer.ainvoke(
        {"phone_number": "98765 43210", "account_holder_name": "priya"}, config
    )
    assert "Priya Sharma" in result

    bill = await get_latest_bill.ainvoke({}, config)
    assert "International roaming pack" in bill
    assert "unpaid" in bill

    usage = await get_usage.ainvoke({}, config)
    assert "Data: used" in usage

    overview = await get_account_overview.ainvoke({}, config)
    assert "Lauki Premium 2GB" in overview


async def test_caller_id_identifies_customer_automatically():
    call, created = await calls.get_or_create_call(
        f"test-{uuid.uuid4()}", channel=CallChannel.phone, caller_number="+919812345678"
    )
    assert created
    customer = await calls.get_call_customer(call.id)
    assert customer is not None and customer.full_name == "Rahul Verma"
