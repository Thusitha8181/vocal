"""Retrieval quality checks: each question must surface the right document in the top 3."""

import pytest

from app.config import get_settings
from app.rag.ingest import load_pdf
from app.rag.store import asearch

CASES = [
    ("Why is my bill higher than my plan price this month?", "lauki-billing-faq.pdf"),
    ("What happens if I miss my postpaid due date?", "lauki-billing-faq.pdf"),
    ("How long do refunds take?", "lauki-billing-faq.pdf"),
    ("Can I switch from prepaid to postpaid?", "lauki-billing-faq.pdf"),
    ("Which plan comes with Netflix and Amazon Prime Video?", "lauki-plans.pdf"),
    ("How much does the cheapest prepaid plan cost?", "lauki-plans.pdf"),
    ("Is 5G available in Bangalore?", "lauki-network-coverage.pdf"),
    ("My signal is weak indoors, what should I do?", "lauki-network-coverage.pdf"),
    ("When will Jaipur get 5G?", "lauki-network-coverage.pdf"),
]


def test_plan_sections_are_not_split_across_pages():
    _, pages, docs = load_pdf(get_settings().knowledge_dir / "lauki-plans.pdf")
    assert pages == 3
    premium = next(d for d in docs if "Lauki Premium 2GB" in d.page_content)
    assert "Price: Rs. 449" in premium.page_content
    assert "2 GB" in premium.page_content.split("Lauki Premium 2GB", 1)[1]


@pytest.mark.parametrize(("question", "expected_source"), CASES)
async def test_top3_contains_expected_source(knowledge, question, expected_source):
    results = await asearch(question, k=3)
    assert expected_source in [r.source for r in results], [(r.source, r.score) for r in results]
