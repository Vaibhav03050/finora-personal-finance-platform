"""
AI Money Coach.

Architecture (never violated): transactions -> deterministic analytics ->
structured insight dict -> [optional LLM] -> natural language.

The LLM (if configured) is given ONLY the structured numbers already
computed elsewhere and is instructed to explain them, not calculate new
ones. If no API key is configured, deterministic templates answer instead,
so the whole app works with zero AI spend.
"""
import re
from typing import Optional

import httpx

from app.config import settings
from app.services.money import to_major

SYSTEM_PROMPT = (
    "You are Finora's Money Coach, a personal finance education and coaching "
    "assistant. Answer in warm, simple, non-technical language (a curious "
    "teenager should understand). Assume an India/INR context unless the user "
    "indicates otherwise.\n\n"
    "You may be given a JSON object of ALREADY-COMPUTED figures for this user.\n"
    "STRICT RULE about that JSON: never invent, estimate or recalculate any "
    "user-specific number. Only cite figures present in the JSON. If a "
    "user-specific number needed to answer is missing, say that data isn't "
    "available yet and explain what the user would need to add - never guess "
    "their income, balances, transactions or goals.\n\n"
    "You SHOULD still answer general personal-finance questions (budgeting, "
    "saving, credit scores, deposits, SIPs, mutual funds, insurance, loans, "
    "compound interest, taxes and similar) using your own general knowledge, "
    "even when the JSON is empty - those are educational answers, not claims "
    "about the user's data.\n\n"
    "Be clear about the difference between general education and personalized "
    "guidance. Never promise or guarantee investment returns, and don't "
    "present yourself as a licensed financial advisor for high-stakes "
    "decisions. Ask a clarifying question when the request is ambiguous. If a "
    "question is unrelated to money or personal finance, politely say that's "
    "outside what you help with. Keep answers under 150 words."
)


def _call_llm(question: str, context: dict) -> Optional[str]:
    if settings.FIN_AI_PROVIDER == "none" or not settings.FIN_AI_API_KEY:
        return None
    try:
        resp = httpx.post(
            f"{settings.FIN_AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.FIN_AI_API_KEY}"},
            json={
                "model": settings.FIN_AI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"DATA: {context}\n\nQUESTION: {question}"},
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # fall through to deterministic template


MAX_QUESTION_CHARS = 1000

OFF_TOPIC_REPLY = (
    "I'm Finora's personal finance coach, so that one's outside what I cover. "
    "I can help with your spending, savings, and goals, plus budgeting, "
    "investments, loans, credit and other money questions. What would you "
    "like to know?"
)

# --- General personal-finance knowledge base -----------------------------
# The coach previously answered only a handful of hardcoded prompts, so any
# other personal-finance question fell through to the generic capability
# message. These entries cover the common educational questions users
# actually type. Each entry is (trigger phrases, answer). The first entry
# whose phrases all appear in the normalized question wins, so more specific
# comparisons are listed before the single-topic entries they mention.
#
# Answers are deliberately general education, never personalized advice, and
# never quote or imply any figure from the user's own account.
_KNOWLEDGE_BASE: list[tuple[tuple[tuple[str, ...], ...], str]] = [
    # --- Comparisons (must precede their single-topic entries) ---
    (
        (("savings account", "saving account", "savings"), ("fixed deposit", "fd", "term deposit")),
        "A savings account keeps money available any time and pays a small amount of "
        "interest, so it suits everyday money and your emergency fund. A fixed deposit "
        "locks a lump sum in for a chosen period at a rate agreed upfront - usually "
        "higher than a savings account - but withdrawing early normally costs you some "
        "interest as a penalty. Rough rule: money you might need this month belongs in "
        "savings; money you're confident you won't touch for a fixed stretch can earn "
        "more in an FD. Both are low-risk; neither is designed for long-term growth.",
    ),
    (
        (("debit card", "debit"), ("credit card", "credit")),
        "A debit card spends money you already have - it pulls straight from your bank "
        "account, so you can't spend beyond your balance. A credit card borrows from the "
        "bank up to a limit, and you repay later. If you clear the full statement amount "
        "by the due date you normally pay no interest; if you pay only the minimum, the "
        "remaining balance is charged at a high rate that builds up quickly. Credit cards "
        "also build your credit history, which debit cards don't.",
    ),
    (
        (("invest", "investing", "investment"), ("saving", "savings", "save")),
        "Saving is keeping money safe and easy to reach - a savings account or FD, where "
        "the amount barely moves. Investing means putting money into things like mutual "
        "funds or stocks for potentially higher growth, accepting that the value can fall "
        "as well as rise. The usual sequence is to build an emergency cushion in savings "
        "first, then invest money you won't need for several years. Longer time horizons "
        "give investments more room to ride out the dips.",
    ),
    # --- Single topics ---
    (
        (("credit score", "cibil", "credit rating", "credit history"),),
        "A credit score is a number lenders use to judge how reliably you repay borrowed "
        "money. In India it's commonly the CIBIL score, ranging roughly 300-900, with "
        "higher being better. The things that usually help most: paying every EMI and "
        "credit card bill in full and on time, keeping your card usage well below the "
        "limit, not applying for lots of credit at once, and keeping older accounts open "
        "so your history looks long. Missed payments hurt the most and take time to "
        "recover from - scores move slowly, over months rather than days.",
    ),
    (
        (("compound interest", "compounding", "compound"),),
        "Compound interest means the returns your money earns start earning returns too. "
        "Simple interest only ever pays on your original amount; compounding pays on the "
        "original amount plus everything it has already earned, so growth accelerates the "
        "longer it runs. For example, money earning a steady annual return roughly "
        "doubles in about 72 divided by that rate in years - at 8%, around nine years. "
        "That's why starting earlier matters more than starting bigger. Note it works "
        "against you on debt too: unpaid credit card balances compound the same way. "
        "You can try different periods in the Simulator.",
    ),
    (
        (("emergency fund", "rainy day", "emergency saving"),),
        "An emergency fund is money set aside only for genuine surprises - a medical "
        "bill, job loss, or urgent repair - so you don't have to borrow or sell "
        "investments in a hurry. A common target is 3-6 months of your regular essential "
        "expenses, leaning toward six if your income is irregular. Keep it somewhere you "
        "can reach quickly, like a savings account, rather than locked into investments. "
        "Building the first month's worth is the hardest part; start with a small fixed "
        "amount each month.",
    ),
    (
        (("mutual fund", "mutual funds"),),
        "A mutual fund pools money from many investors and a professional manager invests "
        "it as one pot, so you get a spread of holdings without picking individual stocks "
        "yourself. Equity funds invest mainly in shares - higher potential growth, bigger "
        "swings. Debt funds invest in bonds and similar - steadier, lower expected "
        "return. Hybrid funds mix both. You can invest a lump sum or a fixed amount "
        "monthly through an SIP. Returns aren't guaranteed and the value can fall, so "
        "they suit money you can leave invested for several years.",
    ),
    (
        (("sip", "systematic investment"),),
        "An SIP (Systematic Investment Plan) is simply investing a fixed amount at regular "
        "intervals - usually monthly - instead of one lump sum. It builds the habit "
        "automatically and means you buy at a range of prices over time rather than "
        "betting on one entry point, which smooths out some of the ups and downs. You can "
        "usually start small and stop or change the amount later. It doesn't guarantee "
        "returns - the underlying fund can still fall in value.",
    ),
    (
        (("fixed deposit", "fd ", " fd", "recurring deposit", "term deposit"),),
        "A fixed deposit means handing a bank a lump sum for a set period at an interest "
        "rate agreed upfront. It's low-risk and predictable, which makes it useful for "
        "money you'll need on a known date. The trade-offs: withdrawing early usually "
        "costs you part of the interest, and the return is often modest once inflation is "
        "taken into account. A recurring deposit works the same way but you pay in a "
        "fixed amount monthly instead of one lump sum.",
    ),
    (
        (("budget", "budgeting", "50/30/20", "50 30 20"),),
        "A budget is just deciding where your money goes before the month starts, instead "
        "of finding out afterwards. A popular starting structure is 50/30/20: roughly 50% "
        "to needs (rent, food, bills, EMIs), 30% to wants, and 20% to savings and debt "
        "repayment. Treat it as a reference point rather than a rule - if rent is high "
        "where you live, the shares shift. The practical step is to look at what you "
        "actually spent last month by category, then set a few realistic limits. Your "
        "spending breakdown in Finora is a good place to start.",
    ),
    (
        (("inflation",),),
        "Inflation is the general rise in prices over time, which means the same money "
        "buys a little less each year. If prices rise around 6% a year, something costing "
        "₹100 today costs about ₹106 next year. This matters for savings: if your money "
        "earns less than inflation, it's quietly losing purchasing power even though the "
        "balance looks unchanged. It's the main reason long-term money is usually "
        "invested rather than left entirely in a savings account.",
    ),
    (
        (("insurance", "term plan", "health cover", "mediclaim"),),
        "Insurance protects you from costs big enough to derail your finances. Health "
        "insurance covers hospital bills; term life insurance pays your dependents a lump "
        "sum if you die during the policy period and is usually the cheapest way to get "
        "meaningful life cover. A common principle is to insure what you couldn't afford "
        "to pay for yourself, and to keep insurance separate from investing - mixed "
        "policies often deliver weaker cover and weaker returns than buying each "
        "separately. Cover amounts depend a lot on your dependents and liabilities.",
    ),
    (
        (("emi", "loan", "borrow", "repay"),),
        "An EMI (Equated Monthly Installment) is the fixed monthly payment that repays a "
        "loan, made up of interest plus a slice of the principal. Early EMIs are mostly "
        "interest; later ones mostly principal. Two things decide the real cost: the "
        "interest rate and the tenure - a longer tenure lowers the monthly payment but "
        "increases the total interest you pay overall. Lenders also look at how much of "
        "your income already goes to EMIs. Clearing high-interest debt, like credit card "
        "balances, usually beats investing the same money.",
    ),
    (
        (("tax", "80c", "income tax", "tds"),),
        "In India income tax is charged in slabs, and you choose between the old regime "
        "(lower slabs offset by deductions such as 80C, HRA and health premiums) and the "
        "new regime (wider slabs but almost no deductions). Which works out cheaper "
        "depends on how many deductions you'd actually claim. Slab rates and limits are "
        "revised from time to time, so check the current year's figures before deciding, "
        "and consider a qualified tax professional for anything complex - I can explain "
        "the concepts but I can't file or optimize a return for you.",
    ),
    (
        (("diversif", "spread my money", "all my eggs"),),
        "Diversification means spreading money across different investments so one bad "
        "outcome doesn't sink the whole plan. Different assets - shares, bonds, gold, "
        "deposits - tend not to fall at the same time or by the same amount. A single "
        "mutual fund already holds many companies, which is one reason funds are a common "
        "starting point. It reduces the damage from any one holding going wrong; it "
        "doesn't remove risk altogether.",
    ),
    (
        (("risk",),),
        "Risk is the chance an investment's value falls rather than rises. Generally, "
        "higher potential growth comes with bigger swings along the way. Two things "
        "shape how much risk suits you: how long before you need the money, and how "
        "you'd react to seeing the value drop. Money you need within a year or two "
        "usually belongs somewhere stable; money you won't touch for many years can "
        "absorb more ups and downs in exchange for higher expected growth.",
    ),
    (
        (("net worth",),),
        "Net worth is everything you own minus everything you owe - savings, investments "
        "and property on one side, loans and card balances on the other. It's a useful "
        "single number because it captures progress that income alone hides: paying down "
        "a loan raises net worth even though nothing new was saved. What matters is the "
        "direction over months, not the figure on any one day.",
    ),
    (
        (("gold",),),
        "Gold is usually held as a hedge - it often holds value when other assets struggle "
        "- rather than as a growth engine, since it produces no interest or dividends. "
        "Besides jewellery, it can be held through sovereign gold bonds, gold ETFs or "
        "gold mutual funds, which avoid storage and making charges. It's commonly treated "
        "as a modest slice of a portfolio rather than its core.",
    ),
    (
        (
            ("cut", "reduce", "cut down", "trim", "spend less"),
            ("spend", "spending", "expense", "expenses", "₹", "money", "budget",
             "this month", "each month", "every month", "monthly", "bills", "cost"),
        ),
        "The reliable way to cut spending is to start from what you actually spent rather "
        "than guesswork. Look at your biggest categories first - a 10% trim on a large "
        "category beats eliminating a small one. Recurring costs are usually the easiest "
        "win because you only decide once: unused subscriptions, plans you've outgrown, "
        "cashback or fees you're not using. Then pick one or two discretionary categories "
        "to cap rather than trying to cut everything at once. Your category breakdown and "
        "the 'Where can I save' view show which categories are worth looking at.",
    ),
    (
        (("retire", "retirement", "pension", "nps", "epf", "ppf"),),
        "Retirement planning is about building an amount large enough to cover your "
        "expenses once you stop earning. The two things that matter most are how early "
        "you start and how consistently you contribute, because compounding needs time. "
        "In India the common building blocks are EPF (salaried, employer-matched), PPF (a "
        "long-term government-backed account with a lock-in), and NPS (a retirement "
        "account with market-linked options). How much you need depends heavily on your "
        "expenses and retirement age, so treat any single number you read as a starting "
        "point rather than a target.",
    ),
]

# Vocabulary used only to decide whether an unmatched question is about money
# at all. A question with none of these words gets the polite off-topic
# reply instead of the capability message.
_FINANCE_VOCAB = {
    "money", "finance", "financial", "spend", "spending", "spent", "save", "saving",
    "savings", "invest", "investing", "investment", "bank", "banking", "loan", "emi",
    "debt", "borrow", "tax", "taxes", "budget", "budgeting", "salary", "income",
    "expense", "expenses", "rupee", "rupees", "inr", "credit", "debit", "card",
    "fund", "funds", "interest", "insurance", "account", "goal", "goals", "retire",
    "retirement", "pension", "afford", "cash", "upi", "deposit", "fd", "sip", "nps",
    "epf", "ppf", "cost", "price", "bill", "bills", "rent", "wealth", "profit",
    "loss", "return", "returns", "inflation", "portfolio", "stock", "stocks",
    "share", "shares", "mutual", "gold", "balance", "cibil", "payment", "pay",
    "earn", "earning", "earnings", "wallet", "atm", "cheque", "overdraft", "pf",
}


def _normalize_question(text: str) -> str:
    return re.sub(r"[^a-z0-9₹/ ]+", " ", (text or "").lower())


def _knowledge_answer(question: str) -> Optional[str]:
    """Returns a general personal-finance explanation when the question
    matches a knowledge-base entry. Entries require every phrase group to be
    present, so comparison questions ('savings account vs FD') match the
    comparison entry rather than either single-topic entry."""
    norm = " " + re.sub(r"\s+", " ", _normalize_question(question)).strip() + " "
    for groups, response in _KNOWLEDGE_BASE:
        if all(any(phrase in norm for phrase in group) for group in groups):
            return response
    return None


def _looks_finance_related(question: str) -> bool:
    norm = _normalize_question(question)
    if "₹" in question:
        return True
    words = set(re.findall(r"[a-z0-9]+", norm))
    return bool(words & _FINANCE_VOCAB)


def _fmt(minor: int) -> str:
    return f"₹{to_major(minor):,.0f}"


def _fmt_pct(pct) -> str:
    if pct is None:
        return "0"
    return f"{pct:.0f}" if float(pct).is_integer() else f"{pct:.1f}"


def _template_answer(question: str, ctx: dict) -> str:
    q = question.lower()

    if any(k in q for k in ["where did my money go", "where does my money go", "spending breakdown"]):
        tops = ctx.get("top_categories", [])
        if not tops:
            return "I don't have enough transactions yet to break down your spending. Try adding a few expenses first."
        lines = [f"{t['category']}: {_fmt(t['average_monthly_minor'])}/month" for t in tops[:3]]
        return "Here's where most of your money has been going recently:\n" + "\n".join(lines)

    if any(k in q for k in ["not saving enough", "why am i not saving", "no savings", "how can i save", "save more", "ways to save"]):
        rate = ctx.get("savings_rate", 0)
        return (
            f"Right now you're saving about {rate*100:.0f}% of your income. "
            "That usually happens when regular expenses or discretionary spending "
            "(like shopping or eating out) take up a big share of what comes in. "
            "Check the 'Where can I save' tab for specific categories to look at."
        )

    # "Where can I cut ₹2,000 this month?" is one of the coach's own example
    # questions. Answer it from the user's real categories when we have them,
    # and let the general knowledge base handle it when we don't.
    if any(k in q for k in ["where can i cut", "cut back", "cut down", "where to cut"]):
        tops = ctx.get("top_categories", [])
        if tops:
            lines = [f"{t['category']}: {_fmt(t['average_monthly_minor'])}/month" for t in tops[:3]]
            return (
                "Your largest categories are where a cut goes furthest:\n"
                + "\n".join(lines)
                + "\n\nTrimming a set percentage from the biggest one is usually easier "
                "than cutting several small categories to zero. Recurring costs like "
                "unused subscriptions are the simplest place to start."
            )

    if any(k in q for k in ["afford", "can i buy"]):
        gap = ctx.get("goal_gap_minor")
        if gap is None:
            return "Tell me about a specific goal (amount + date) and I can tell you if it's realistic based on your current saving pace."
        if gap <= 0:
            return "Based on your current numbers, this looks achievable if you keep up your current saving pace. 🎉"
        return f"Based on your current spending, you'd still need about {_fmt(gap)} more per month to hit this comfortably."

    if any(k in q for k in ["how much should i save", "save next month", "saving plan"]):
        req = ctx.get("required_monthly_minor")
        if req is None:
            return (
                "I don't have a goal to work from yet, so I can't give you a figure "
                "based on your own numbers. As a general starting point, many people "
                "aim for around 20% of take-home pay toward savings and debt "
                "repayment, adjusting down if essentials take up more. Set up a goal "
                "and I can tell you exactly how much to save each month for it."
            )
        return f"To stay on track for your goal, aim to save about {_fmt(req)} next month."

    if any(k in q for k in ["behind my goal", "am i on track", "goal status"]):
        status = ctx.get("goal_status")
        if not status:
            return "You don't have an active goal tracked yet - create one and I can track your progress."
        explanations = {
            "ahead": "You're ahead of schedule on your goal. Nice work! 🟢",
            "on_track": "You're right on track for your goal. 🔵",
            "slightly_behind": f"You're slightly behind this month. {ctx.get('shortfall_reason', '')} 🟡",
            "behind": f"You're behind this month's target. {ctx.get('shortfall_reason', '')} 🔴",
            "achieved": "You've already reached this goal! 🎉",
        }
        return explanations.get(status, "I couldn't determine your goal status.")

    if any(k in q for k in ["expenses increased", "expenses increase", "spending increased", "spending increase", "what increased", "what's increased"]):
        trends = ctx.get("increasing_categories", [])
        if not trends:
            return "Nothing stands out as having increased significantly recently - your spending looks fairly stable."
        lines = [f"{t['category']} (+{_fmt_pct(t['change_pct'])}%)" for t in trends[:3]]
        return "These categories increased compared to your usual spending: " + ", ".join(lines)

    if any(k in q for k in ["learn about investing", "should i invest", "start investing", "how to invest", "learn to invest", "learn investing"]):
        return (
            "Good instinct to ask before jumping in. Investing means putting money "
            "to work for potentially higher growth, in exchange for more risk than "
            "plain saving - and it's usually best once you already have some "
            "emergency savings set aside. Head to the Learn Money tab for plain-language "
            "explanations of SIP, mutual funds, risk, and diversification. "
            "(This isn't personalized investment advice.)"
        )

    if "emergency fund" in q:
        return (
            "An emergency fund is money set aside for surprises - a medical bill, "
            "job loss, or urgent repair - so you don't have to borrow or sell "
            "investments in a hurry. A common starting target is 3-6 months of "
            "your regular expenses, kept somewhere easy to access."
        )

    if "sip" in q:
        return (
            "SIP (Systematic Investment Plan) just means investing a fixed amount "
            "regularly - like a monthly subscription, but for investing - instead "
            "of putting in one lump sum. It helps build the habit and smooths out "
            "the ups and downs of the market over time. It doesn't guarantee returns."
        )

    # No personalized intent matched. Try the general personal-finance
    # knowledge base before giving up, so free-text educational questions
    # ("what is a credit score?", "savings account vs FD") are answered
    # instead of falling through to the capability message.
    knowledge_answer = _knowledge_answer(q)
    if knowledge_answer:
        return knowledge_answer

    if not _looks_finance_related(q):
        return OFF_TOPIC_REPLY

    return (
        "I can help with your spending, savings, and goals using your actual "
        "numbers. Try asking things like 'Where did my money go?' or "
        "'How much should I save next month?'"
    )


def answer(question: str, context: dict) -> dict:
    question = (question or "").strip()
    if not question:
        return {
            "answer": (
                "Ask me anything about your money - budgeting, saving, your goals, "
                "or how something like a credit score or an SIP works."
            ),
            "source": "template",
        }
    # Guard against very long inputs reaching the LLM or the matcher.
    question = question[:MAX_QUESTION_CHARS]

    llm_answer = _call_llm(question, context)
    if llm_answer:
        return {"answer": llm_answer, "source": "ai"}
    return {"answer": _template_answer(question, context), "source": "template"}
