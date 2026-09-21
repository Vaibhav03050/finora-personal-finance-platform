from fastapi import APIRouter

from app.schemas import CompoundSimRequest, ok
from app.services.money import to_major, to_minor
from app.services.simulator import simulate_compound_growth

router = APIRouter(prefix="/api/v1/simulator", tags=["simulator"])


@router.post("/compound-growth")
def compound_growth(payload: CompoundSimRequest):
    result = simulate_compound_growth(
        to_minor(payload.monthly_contribution_rupees), payload.years, payload.annual_return_pct,
    )
    return ok({
        "months": result["months"],
        "total_contribution_rupees": to_major(result["total_contribution_minor"]),
        "future_value_rupees": to_major(result["future_value_minor"]),
        "growth_rupees": to_major(result["growth_minor"]),
        "disclaimer": result["disclaimer"],
    })


INVESTMENT_COMPARISON = [
    {"option": "Emergency savings", "risk": "Low", "horizon": "Short", "liquidity": "High", "purpose": "Emergencies"},
    {"option": "Fixed Deposit (FD)", "risk": "Lower", "horizon": "Short/Medium", "liquidity": "Medium", "purpose": "Stability"},
    {"option": "Recurring Deposit (RD)", "risk": "Lower", "horizon": "Short/Medium", "liquidity": "Medium", "purpose": "Regular saving"},
    {"option": "SIP in a mutual fund", "risk": "Market-linked", "horizon": "Long", "liquidity": "Medium", "purpose": "Long-term investing"},
    {"option": "Equity-oriented investments", "risk": "Higher", "horizon": "Long", "liquidity": "Medium", "purpose": "Growth"},
    {"option": "Diversified funds", "risk": "Varies", "horizon": "Long", "liquidity": "Medium", "purpose": "Long-term balance"},
]


@router.get("/investment-comparison")
def investment_comparison():
    return ok({
        "rows": INVESTMENT_COMPARISON,
        "disclaimer": "Educational comparison only - not personalized investment advice, and no option is guaranteed to be best for you.",
    })
