"""
Tool: calculate_refund

Implements the refund calculation formula from knowledge_base/refund_policy.md:

    refund_amount = (days_remaining_in_cycle / total_days_in_cycle) * amount_charged

This is a genuine business-logic tool (not just a documentation lookup) —
it's the kind of deterministic calculation you want a TOOL to do rather than
asking an LLM to do arithmetic in free text, since LLMs are unreliable at
precise math and a refund amount is exactly the kind of number that must be
correct every time.
"""

from pydantic import BaseModel, Field

from backend.utils.logger import logger


class CalculateRefundInput(BaseModel):
    amount_charged: float = Field(..., gt=0, description="The original amount charged, in dollars")
    days_remaining_in_cycle: int = Field(..., ge=0, description="Days left in the current billing cycle")
    total_days_in_cycle: int = Field(default=30, gt=0, description="Total length of the billing cycle in days")
    reason: str = Field(default="customer_request", description="Reason for the refund, e.g. 'duplicate_charge', 'outage'")
    outage_hours: float = Field(default=0.0, ge=0, description="Hours of confirmed outage, if reason is 'outage'")


def calculate_refund(
    amount_charged: float,
    days_remaining_in_cycle: int,
    total_days_in_cycle: int = 30,
    reason: str = "customer_request",
    outage_hours: float = 0.0,
) -> dict:
    """
    Calculates a refund amount according to TechNova Cloud's refund policy.

    Two formulas, matching the policy document:
      - Standard proration: (days_remaining / total_days) * amount_charged
      - Outage credit: (outage_hours / 720) * amount_charged, capped at amount_charged

    Returns a breakdown dict so the agent can explain the calculation
    transparently to the customer, rather than just stating a number.
    """
    logger.info(
        "Tool called: calculate_refund(amount={}, days_remaining={}, total_days={}, reason='{}')",
        amount_charged, days_remaining_in_cycle, total_days_in_cycle, reason,
    )

    if days_remaining_in_cycle > total_days_in_cycle:
        raise ValueError("days_remaining_in_cycle cannot exceed total_days_in_cycle")

    if reason == "outage" and outage_hours > 0:
        # 720 = approx hours in a 30-day month, matching the policy doc.
        raw_refund = (outage_hours / 720) * amount_charged
        refund_amount = min(raw_refund, amount_charged)
        formula = f"({outage_hours} outage_hours / 720) * ${amount_charged:.2f}"
    else:
        proration_ratio = days_remaining_in_cycle / total_days_in_cycle
        refund_amount = proration_ratio * amount_charged
        formula = (
            f"({days_remaining_in_cycle} days_remaining / {total_days_in_cycle} total_days) "
            f"* ${amount_charged:.2f}"
        )

    refund_amount = round(refund_amount, 2)

    return {
        "refund_amount": refund_amount,
        "currency": "USD",
        "formula": formula,
        "reason": reason,
        "message": (
            f"Based on our refund policy, the calculated refund is ${refund_amount:.2f} "
            f"({formula} = ${refund_amount:.2f})."
        ),
    }
