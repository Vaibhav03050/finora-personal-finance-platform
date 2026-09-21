"""
Categorization pipeline: RuleEngine first (keyword/regex merchant mapping),
then a TF-IDF + LogisticRegression ML fallback for unknown merchants.

categorySource is always stored so the UI can show provenance, and users
can always override manually.
"""
import logging
import re
from pathlib import Path
from typing import Optional

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger("finora")

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "categorizer.joblib"
LOW_CONFIDENCE_THRESHOLD = 0.45

# --- Category icon map (used by frontend too) ---
CATEGORY_ICONS = {
    "Food": "🍔", "Shopping": "🛍", "Home": "🏠", "Transport": "🚗",
    "Bills": "💡", "Education": "🎓", "Health": "🏥", "Entertainment": "🎬",
    "Recharge": "📱", "Income": "💰", "Other": "📦",
}

# Essential vs flexible/discretionary classification, used by goal planning
ESSENTIAL_CATEGORIES = {"Bills", "Home", "Health", "Education"}
FLEXIBLE_CATEGORIES = {"Food", "Transport", "Recharge"}
DISCRETIONARY_CATEGORIES = {"Shopping", "Entertainment", "Other"}

# --- Rule engine: keyword -> category (case-insensitive substring match) ---
RULES: dict[str, str] = {
    "amazon": "Shopping", "flipkart": "Shopping", "myntra": "Shopping", "ajio": "Shopping",
    "swiggy": "Food", "zomato": "Food", "restaurant": "Food", "cafe": "Food", "dominos": "Food",
    "uber": "Transport", "ola": "Transport", "rapido": "Transport", "petrol": "Transport",
    "fuel": "Transport", "irctc": "Transport", "metro": "Transport",
    "netflix": "Entertainment", "spotify": "Entertainment", "hotstar": "Entertainment",
    "prime video": "Entertainment", "bookmyshow": "Entertainment", "movie": "Entertainment",
    "electricity": "Bills", "water bill": "Bills", "broadband": "Bills", "wifi": "Bills",
    "gas bill": "Bills", "insurance": "Bills", "emi": "Bills", "loan": "Bills",
    "rent": "Home", "maintenance": "Home", "furniture": "Home",
    "recharge": "Recharge", "airtel": "Recharge", "jio": "Recharge", "vi ": "Recharge",
    "tuition": "Education", "course": "Education", "udemy": "Education", "coursera": "Education",
    "school fee": "Education", "college": "Education",
    "hospital": "Health", "pharmacy": "Health", "medicine": "Health", "doctor": "Health",
    "clinic": "Health", "apollo": "Health",
    "salary": "Income", "stipend": "Income", "bonus": "Income", "refund": "Income",
    "interest credit": "Income", "freelance": "Income",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def rule_categorize(text: str) -> Optional[str]:
    norm = normalize_text(text)
    for keyword, category in RULES.items():
        if keyword in norm:
            return category
    return None


# --- ML fallback ---
# A small labeled seed set covers vocabulary the rule engine misses.
# It is intentionally separate from user data (see rule #48: no fake prod data).
_SEED_TRAINING_DATA = [
    ("big billion day sale order", "Shopping"), ("clothing store purchase", "Shopping"),
    ("shoe store", "Shopping"), ("online shopping cart", "Shopping"), ("mall purchase", "Shopping"),
    ("lunch with friends", "Food"), ("dinner order", "Food"), ("grocery store", "Food"),
    ("supermarket bill", "Food"), ("bakery", "Food"), ("street food vendor", "Food"),
    ("cab ride", "Transport"), ("bus ticket", "Transport"), ("train ticket", "Transport"),
    ("parking fee", "Transport"), ("toll payment", "Transport"), ("bike service", "Transport"),
    ("gaming subscription", "Entertainment"), ("concert ticket", "Entertainment"),
    ("streaming service", "Entertainment"), ("club entry", "Entertainment"),
    ("mobile bill payment", "Bills"), ("internet bill", "Bills"), ("dth recharge", "Bills"),
    ("society maintenance", "Home"), ("home repair", "Home"), ("furniture purchase", "Home"),
    ("prepaid mobile recharge", "Recharge"), ("data pack", "Recharge"),
    ("online course fee", "Education"), ("book purchase", "Education"), ("exam fee", "Education"),
    ("hospital bill", "Health"), ("gym membership", "Health"), ("dental checkup", "Health"),
    ("monthly salary credit", "Income"), ("cashback credit", "Income"), ("dividend credit", "Income"),
    ("misc payment", "Other"), ("atm withdrawal", "Other"), ("bank charges", "Other"),
]


def _train_and_save_model() -> Pipeline:
    texts = [t for t, _ in _SEED_TRAINING_DATA]
    labels = [c for _, c in _SEED_TRAINING_DATA]
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    pipeline.fit(texts, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    return pipeline


_model: Optional[Pipeline] = None


def get_model() -> Pipeline:
    global _model
    if _model is not None:
        return _model
    if MODEL_PATH.exists():
        _model = joblib.load(MODEL_PATH)
    else:
        _model = _train_and_save_model()
    return _model


def ml_categorize(text: str) -> tuple[str, float]:
    model = get_model()
    norm = normalize_text(text)
    proba = model.predict_proba([norm])[0]
    classes = model.classes_
    best_idx = proba.argmax()
    return classes[best_idx], float(proba[best_idx])


def categorize(text: str) -> tuple[str, str, float]:
    """
    Returns (category, category_source, confidence).
    Rule engine wins deterministically when it matches; otherwise ML fallback;
    otherwise "Other" with low confidence for manual review.

    The ML step is intentionally best-effort: a corrupted model file, a
    scikit-learn version mismatch, or any other model-loading/prediction
    failure must never abort statement import (a single un-ruled merchant
    line used to be able to fail an entire PDF upload). On any such error we
    log it and fall back to "Other" so the transaction still comes through
    for manual review.
    """
    rule_hit = rule_categorize(text)
    if rule_hit:
        return rule_hit, "rule", 1.0

    try:
        category, confidence = ml_categorize(text)
    except Exception:
        logger.exception("ML categorization failed; falling back to 'Other'.")
        return "Other", "ml_unavailable", 0.0

    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return "Other", "ml", confidence
    return category, "ml", confidence
