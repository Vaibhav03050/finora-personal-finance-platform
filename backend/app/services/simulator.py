"""
Illustrative SIP / compound-growth simulator. Pure deterministic math.
Always surfaced to the user with an "illustrative, not guaranteed" label -
see rule #27 and #44 (responsible AI / no guaranteed returns).
"""
from app.services.money import to_minor


def simulate_compound_growth(monthly_contribution_minor: int, years: float, annual_return_pct: float) -> dict:
    months = round(years * 12)
    monthly_rate = (annual_return_pct / 100) / 12

    total_contribution_minor = monthly_contribution_minor * months

    if monthly_rate == 0:
        future_value_minor = total_contribution_minor
    else:
        # Future value of an ordinary monthly SIP, contribution at month end.
        future_value = monthly_contribution_minor * (
            (((1 + monthly_rate) ** months) - 1) / monthly_rate
        ) * (1 + monthly_rate)
        future_value_minor = round(future_value)

    growth_minor = future_value_minor - total_contribution_minor

    return {
        "months": months,
        "total_contribution_minor": total_contribution_minor,
        "future_value_minor": future_value_minor,
        "growth_minor": growth_minor,
        "disclaimer": "Illustrative scenario only. Actual returns are not guaranteed and can be lower or negative.",
    }
