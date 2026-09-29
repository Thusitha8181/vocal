"""Seed mock Lauki Phones plans, customers, bills and usage.

Dates are relative to today so the demo scenarios (bill due soon, overdue, prepaid expiring)
stay realistic whenever the seed is run. Set DEMO_CUSTOMER_PHONE to map your own phone number
to the first customer so a real Twilio call from your phone is recognised by caller ID.
"""

import asyncio
import os
from datetime import date, timedelta
from typing import Any

from sqlmodel import delete, select

from app.db.models import (
    AccountStatus,
    Bill,
    BillStatus,
    ConnectionType,
    Customer,
    Plan,
    Usage,
)
from app.db.session import session_scope

GST_RATE = 0.18

PLANS = [
    Plan(
        code="LITE_500MB",
        name="Lauki Lite 500MB",
        connection_type=ConnectionType.prepaid,
        price_inr=99,
        validity_days=7,
        data_mb=500,
        voice_minutes=100,
        sms=50,
        benefits="Pay-as-you-go rate after limit is used, no long-term commitment.",
    ),
    Plan(
        code="BASIC_1GB",
        name="Lauki Basic 1GB",
        connection_type=ConnectionType.prepaid,
        price_inr=199,
        validity_days=30,
        data_mb=1024,
        voice_minutes=300,
        sms=100,
        benefits="Up to 500MB unused data rolls over. Free incoming calls while roaming in India.",
    ),
    Plan(
        code="PREMIUM_2GB",
        name="Lauki Premium 2GB",
        connection_type=ConnectionType.postpaid,
        price_inr=449,
        validity_days=30,
        data_mb=2048,
        voice_minutes=300,
        sms=100,
        benefits="Free data rollover, priority support queue, one month of Netflix Mobile.",
    ),
    Plan(
        code="ELITE_5GB",
        name="Lauki Elite 5GB",
        connection_type=ConnectionType.postpaid,
        price_inr=899,
        validity_days=30,
        data_mb=5120,
        voice_minutes=1000,
        sms=500,
        benefits="Unlimited data rollover, 24/7 priority support, Netflix and Amazon Prime Video.",
    ),
]


def _bill(
    customer: Customer,
    items: list[tuple[str, float]],
    *,
    period_start: date,
    status: BillStatus,
    paid_on: date | None = None,
) -> Bill:
    subtotal = sum(amount for _, amount in items)
    gst = round(subtotal * GST_RATE, 2)
    line_items: list[dict[str, Any]] = [{"description": d, "amount_inr": a} for d, a in items]
    line_items.append({"description": "GST (18%)", "amount_inr": gst})
    period_end = period_start + timedelta(days=29)
    return Bill(
        customer_id=customer.id,
        period_start=period_start,
        period_end=period_end,
        due_date=period_end + timedelta(days=15),
        amount_inr=round(subtotal + gst, 2),
        status=status,
        line_items=line_items,
        paid_on=paid_on,
    )


def build_customers(today: date) -> tuple[list[Customer], list[Bill], list[Usage]]:
    demo_phone = os.getenv("DEMO_CUSTOMER_PHONE", "").strip() or "+919876543210"

    priya = Customer(
        phone=demo_phone,
        full_name="Priya Sharma",
        email="priya.sharma@example.com",
        city="Hyderabad",
        plan_code="PREMIUM_2GB",
        activated_on=date(2024, 3, 12),
        bill_cycle_day=12,
    )
    rahul = Customer(
        phone="+919812345678",
        full_name="Rahul Verma",
        email="rahul.verma@example.com",
        city="Bangalore",
        plan_code="ELITE_5GB",
        activated_on=date(2023, 7, 1),
        bill_cycle_day=1,
        autopay_enabled=True,
    )
    ananya = Customer(
        phone="+919900112233",
        full_name="Ananya Iyer",
        email="ananya.iyer@example.com",
        city="Mumbai",
        plan_code="BASIC_1GB",
        activated_on=date(2025, 1, 20),
        validity_ends_on=today + timedelta(days=3),
    )
    arjun = Customer(
        phone="+919811122334",
        full_name="Arjun Mehta",
        email="arjun.mehta@example.com",
        city="Delhi",
        plan_code="PREMIUM_2GB",
        account_status=AccountStatus.suspended,
        activated_on=date(2022, 11, 5),
        bill_cycle_day=5,
    )
    sneha = Customer(
        phone="+919822233445",
        full_name="Sneha Reddy",
        email="sneha.reddy@example.com",
        city="Pune",
        plan_code="LITE_500MB",
        account_status=AccountStatus.expired,
        activated_on=date(2025, 6, 2),
        validity_ends_on=today - timedelta(days=4),
    )
    vikram = Customer(
        phone="+919833344556",
        full_name="Vikram Singh",
        email="vikram.singh@example.com",
        city="Jaipur",
        plan_code="ELITE_5GB",
        activated_on=date(2024, 9, 18),
        bill_cycle_day=18,
    )
    customers = [priya, rahul, ananya, arjun, sneha, vikram]

    last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    two_months_ago = (last_month - timedelta(days=1)).replace(day=1)

    bills = [
        # Priya: current bill higher than plan price because of a roaming pack.
        _bill(
            priya,
            [("Lauki Premium 2GB - monthly plan", 449), ("International roaming pack (UAE)", 150)],
            period_start=last_month,
            status=BillStatus.unpaid,
        ),
        _bill(
            priya,
            [("Lauki Premium 2GB - monthly plan", 449)],
            period_start=two_months_ago,
            status=BillStatus.paid,
            paid_on=two_months_ago + timedelta(days=40),
        ),
        # Rahul: autopay, always paid on time.
        _bill(
            rahul,
            [("Lauki Elite 5GB - monthly plan", 899)],
            period_start=last_month,
            status=BillStatus.paid,
            paid_on=today - timedelta(days=2),
        ),
        # Arjun: overdue past the grace period, services suspended, late fee applied.
        _bill(
            arjun,
            [("Lauki Premium 2GB - monthly plan", 449), ("Late payment fee", 50)],
            period_start=two_months_ago,
            status=BillStatus.overdue,
        ),
        # Vikram: mid-cycle plan switch produced a prorated bill.
        _bill(
            vikram,
            [
                ("Lauki Premium 2GB - prorated (12 days)", 179.6),
                ("Lauki Elite 5GB - prorated (18 days)", 539.4),
                ("Extra 1GB data add-on", 49),
            ],
            period_start=last_month,
            status=BillStatus.unpaid,
        ),
    ]
    # Bills generated relative to month boundaries; shift due dates so the current bill is upcoming.
    bills[0].due_date = today + timedelta(days=4)
    bills[4].due_date = today + timedelta(days=9)
    bills[3].due_date = today - timedelta(days=12)

    cycle_start = today.replace(day=1)
    usage = [
        Usage(
            customer_id=priya.id,
            period_start=cycle_start,
            data_used_mb=1650,
            voice_used_minutes=212,
            sms_used=31,
            rollover_data_mb=300,
        ),
        Usage(
            customer_id=rahul.id,
            period_start=cycle_start,
            data_used_mb=3890,
            voice_used_minutes=640,
            sms_used=88,
            rollover_data_mb=2200,
        ),
        Usage(
            customer_id=ananya.id,
            period_start=today - timedelta(days=27),
            data_used_mb=960,
            voice_used_minutes=187,
            sms_used=40,
            rollover_data_mb=120,
        ),
        Usage(
            customer_id=arjun.id,
            period_start=cycle_start,
            data_used_mb=0,
            voice_used_minutes=0,
            sms_used=0,
        ),
        Usage(
            customer_id=sneha.id,
            period_start=today - timedelta(days=11),
            data_used_mb=500,
            voice_used_minutes=74,
            sms_used=12,
        ),
        Usage(
            customer_id=vikram.id,
            period_start=cycle_start,
            data_used_mb=2710,
            voice_used_minutes=455,
            sms_used=120,
            rollover_data_mb=600,
        ),
    ]
    return customers, bills, usage


async def seed() -> None:
    customers, bills, usage = build_customers(date.today())
    async with session_scope() as session:
        for plan in PLANS:
            await session.merge(plan)
        await session.flush()

        phones = [c.phone for c in customers]
        await session.exec(delete(Customer).where(Customer.phone.in_(phones)))  # type: ignore[attr-defined]
        await session.flush()

        session.add_all(customers)
        await session.flush()
        session.add_all(bills + usage)
        await session.commit()

        count = len((await session.exec(select(Customer))).all())
    print(f"Seeded {len(PLANS)} plans and {count} customers.")


if __name__ == "__main__":
    asyncio.run(seed())
