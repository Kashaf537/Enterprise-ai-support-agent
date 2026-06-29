"""
Tests for backend/tools/calculate_refund_tool.py.

This is the most important tool to test thoroughly, since it's exact
arithmetic a customer will personally verify — a wrong refund calculation
is the kind of bug that erodes trust immediately, unlike a slightly
awkwardly-phrased chat response.
"""

import pytest

from backend.tools.calculate_refund_tool import calculate_refund


def test_standard_proration_matches_policy_doc_example():
    # This exact example appears in knowledge_base/refund_policy.md:
    # $199 charge, 20 days remaining of 30 -> $132.67
    result = calculate_refund(amount_charged=199.0, days_remaining_in_cycle=20, total_days_in_cycle=30)
    assert result["refund_amount"] == 132.67


def test_full_refund_when_all_days_remaining():
    result = calculate_refund(amount_charged=50.0, days_remaining_in_cycle=30, total_days_in_cycle=30)
    assert result["refund_amount"] == 50.0


def test_zero_refund_when_no_days_remaining():
    result = calculate_refund(amount_charged=50.0, days_remaining_in_cycle=0, total_days_in_cycle=30)
    assert result["refund_amount"] == 0.0


def test_outage_credit_formula():
    # 6 hours outage / 720 hours in a 30-day month * $199 = $1.6583... -> $1.66
    result = calculate_refund(
        amount_charged=199.0, days_remaining_in_cycle=0, total_days_in_cycle=30,
        reason="outage", outage_hours=6,
    )
    assert result["refund_amount"] == 1.66
    assert result["reason"] == "outage"


def test_outage_credit_capped_at_full_amount():
    # A huge outage (e.g. 1000 hours) should never refund MORE than was charged.
    result = calculate_refund(
        amount_charged=100.0, days_remaining_in_cycle=0, total_days_in_cycle=30,
        reason="outage", outage_hours=1000,
    )
    assert result["refund_amount"] == 100.0


def test_raises_when_days_remaining_exceeds_total_days():
    with pytest.raises(ValueError):
        calculate_refund(amount_charged=100.0, days_remaining_in_cycle=40, total_days_in_cycle=30)


def test_result_includes_human_readable_formula():
    result = calculate_refund(amount_charged=199.0, days_remaining_in_cycle=20, total_days_in_cycle=30)
    assert "$199.00" in result["formula"]
    assert "20" in result["formula"]
    assert "30" in result["formula"]
