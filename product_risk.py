import pickle
import re
import json
import csv
import os
from datetime import datetime
from scipy.sparse import hstack
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enumber_synonyms import normalize_enumbers

# ── Load model artefacts ──────────────────────────────────────────────────────
model           = pickle.load(open("harm_model.pkl",      "rb"))
word_vectorizer = pickle.load(open("word_vectorizer.pkl", "rb"))
char_vectorizer = pickle.load(open("char_vectorizer.pkl", "rb"))
le              = pickle.load(open("label_encoder.pkl",   "rb"))

# ── Severity score per class ──────────────────────────────────────────────────
SEVERITY_SCORE = {
    "safe":           1,
    "moderate":       2,
    "moderately high": 4,
    "hazardous":      7,
}

# ── Confidence threshold ──────────────────────────────────────────────────────
# Predictions below this probability are treated as "unknown" and fall back
# to "moderate" to avoid false confidence on out-of-distribution ingredients.
CONFIDENCE_THRESHOLD = 0.50

# ── Red-flag ingredients ──────────────────────────────────────────────────────
# These always trigger a warning regardless of predicted label or quantity,
# because risk evidence applies even at trace amounts.
RED_FLAG_INGREDIENTS = [
    "titanium dioxide",
    "bha",
    "bht",
    "tbhq",
    "partially hydrogenated",
    "hydrogenated",
    "sodium nitrite",
    "potassium nitrate",
    "nitrite",
    "nitrate",
    "potassium bromate",
    "brominated vegetable oil",
    "artificial color",
    "caramel color",
    "aspartame",
    "propylene glycol",
]

# ── Weight cap ────────────────────────────────────────────────────────────────
# Prevents the first ingredient from dominating the risk score entirely.
# Even if sugar is 80% of a product, it shouldn't mask all other risks.
MAX_INGREDIENT_WEIGHT = 0.40

# ── Unknown ingredient log ────────────────────────────────────────────────────
UNKNOWN_LOG_FILE = "unknown_ingredients_log.csv"


def _log_unknown(product_name: str, ingredient: str, reason: str):
    """Append an unrecognised ingredient to the review log."""
    file_exists = os.path.isfile(UNKNOWN_LOG_FILE)
    with open(UNKNOWN_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "product", "ingredient", "reason"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            product_name,
            ingredient,
            reason,
        ])


def override_label(ingredient: str):
    """
    Hard-coded overrides for ingredients where rule-based certainty
    outperforms the probabilistic model.  Returns label string or None.
    """
    ing = ingredient.lower()

    if "high fructose corn syrup" in ing:
        return "moderately high"
    if "partially hydrogenated" in ing or "hydrogenated" in ing:
        return "hazardous"
    if "nitrite" in ing or "nitrate" in ing:
        return "hazardous"
    if "titanium dioxide" in ing:
        return "hazardous"
    if "bha" in ing or "bht" in ing or "tbhq" in ing:
        return "hazardous"
    if "aspartame" in ing:
        return "moderately high"
    if "high fructose" in ing:
        return "moderately high"
    # Pure sugar synonyms
    for term in ["sugar", "sucrose", "fructose", "dextrose", "glucose syrup",
                 "corn syrup", "maltose"]:
        if term in ing:
            return "moderately high"

    return None


def extract_percentage(raw_ingredient: str):
    """Extract the percentage value from strings like 'sugar (45%)'."""
    match = re.search(r"\((\d+\.?\d*)\s*%\)", raw_ingredient)
    if match:
        return float(match.group(1))
    return None


def is_unknown(ingredient: str, confidence: float) -> bool:
    """
    An ingredient is considered 'unknown' if:
    - The model is below the confidence threshold, OR
    - Fewer than 30% of its word tokens appear in the word vocabulary
      (the ingredient is genuinely out-of-distribution).
    """
    if confidence < CONFIDENCE_THRESHOLD:
        return True

    tokens = ingredient.split()
    if not tokens:
        return True
    known = sum(1 for t in tokens if t in word_vectorizer.vocabulary_)
    return (known / len(tokens)) < 0.3


def predict_with_confidence(ingredient: str):
    """
    Run the dual-vectorizer pipeline and return (label, confidence).
    """
    X_word = word_vectorizer.transform([ingredient])
    X_char = char_vectorizer.transform([ingredient])
    X = hstack([X_word, X_char])
    proba = model.predict_proba(X)[0]
    pred_idx = proba.argmax()
    confidence = proba[pred_idx]
    label = le.inverse_transform([pred_idx])[0]
    return label, confidence


def check_red_flags(ingredient: str):
    """Return list of red-flag terms found in the ingredient string."""
    found = []
    for flag in RED_FLAG_INGREDIENTS:
        if flag in ingredient.lower():
            found.append(flag)
    return found


def analyze_product(product_name: str, ingredient_text: str):
    """
    Full product risk analysis.

    Parameters
    ----------
    product_name    : str — Display name of the product.
    ingredient_text : str — Comma-separated ingredient list, optionally with
                            percentages in parentheses, e.g.
                            "sugar (45%), palm oil (30%), cocoa (15%)"
    """
    print("\n" + "=" * 50)
    print(f"  Product : {product_name}")
    print("=" * 50)

    raw_ingredients = [i.strip() for i in ingredient_text.split(",")]

    total_score  = 0.0
    total_weight = 0.0
    high_risk_count = 0
    red_flags_found = []
    results = []

    for idx, raw_ing in enumerate(raw_ingredients):
        if not raw_ing:
            continue

        # ── Extract percentage and clean ingredient name ──────────────────────
        percent    = extract_percentage(raw_ing)
        ingredient = re.sub(r"\(\d+\.?\d*\s*%\)", "", raw_ing).strip().lower()
        ingredient = normalize_enumbers(ingredient)  # resolve E-numbers

        # ── Determine weight ──────────────────────────────────────────────────
        if percent is not None:
            weight = min(percent / 100.0, MAX_INGREDIENT_WEIGHT)
        else:
            # Position-based fallback (ingredients listed by descending weight)
            weight = min(1.0 / (idx + 1), MAX_INGREDIENT_WEIGHT)

        # ── Red flag check ─────────────────────────────────────────────────────
        flags = check_red_flags(ingredient)
        if flags:
            red_flags_found.extend(flags)

        # ── Classify ──────────────────────────────────────────────────────────
        forced = override_label(ingredient)

        if forced:
            label      = forced
            confidence = 1.0
            method     = "override"

        else:
            ml_label, confidence = predict_with_confidence(ingredient)

            if is_unknown(ingredient, confidence):
                label  = "moderate"
                method = "unknown-fallback"
                _log_unknown(product_name, ingredient,
                             f"confidence={confidence:.2f}")
            else:
                label  = ml_label
                method = f"model({confidence:.2f})"

        severity = SEVERITY_SCORE.get(label, 2)

        if label in ("moderately high", "hazardous"):
            high_risk_count += 1

        total_score  += severity * weight
        total_weight += weight

        # ── Print per-ingredient result ───────────────────────────────────────
        pct_str  = f"({percent}%)" if percent is not None else f"(pos {idx+1})"
        flag_str = " 🚩 RED FLAG" if flags else ""
        print(f"  {ingredient} {pct_str}")
        print(f"      → {label.upper():<16}  confidence: {confidence:.2f}"
              f"  [{method}]{flag_str}")

        results.append({
            "ingredient": ingredient,
            "percent": percent,
            "label": label,
            "confidence": confidence,
            "method": method,
            "red_flag": bool(flags),
        })

    # ── Final score ───────────────────────────────────────────────────────────
    if total_weight == 0:
        print("\n⚠  No valid ingredients to score.")
        return

    avg_score = total_score / total_weight

    # Penalty for multiple high-risk ingredients in the same product
    if high_risk_count >= 3:
        avg_score += 1.5
    elif high_risk_count >= 2:
        avg_score += 1.0

    # Penalty for any red-flag ingredient regardless of proportion
    if red_flags_found:
        avg_score += 0.5

    print("\n" + "-" * 50)
    print(f"  High-risk ingredient count : {high_risk_count}")

    if red_flags_found:
        unique_flags = list(dict.fromkeys(red_flags_found))
        print(f"  🚩 Red flags detected      : {', '.join(unique_flags)}")

    print(f"  Final Risk Score           : {round(avg_score, 2)}")

    if avg_score < 1.4:
        print("  🟢 Overall Product: SAFE PRODUCT")
    elif avg_score < 2.3:
        print("  🟡 Overall Product: MODERATE RISK")
    elif avg_score < 3.3:
        print("  🟠 Overall Product: MODERATELY HIGH RISK")
    else:
        print("  🔴 Overall Product: HAZARDOUS PRODUCT")

    print("=" * 50)

    return {
        "product": product_name,
        "ingredients": results,
        "risk_score": round(avg_score, 2),
        "high_risk_count": high_risk_count,
        "red_flags": list(dict.fromkeys(red_flags_found)),
    }


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    analyze_product(
        "Chocolate Spread",
        "sugar (45%), palm oil (30%), cocoa (15%), milk powder (10%)"
    )

    analyze_product(
        "Flavored Yogurt",
        "milk (70%), sugar (15%), strawberry puree, natural flavor"
    )

    analyze_product(
        "Instant Noodles",
        "wheat flour, palm oil, salt, monosodium glutamate, artificial color"
    )

    analyze_product(
        "Test Product",
        "water, sugar, palm oil, titanium dioxide, bioactive complex"
    )

    analyze_product(
        "E-number Test",
        "water, e621, e150d, e320, e471, e951"
    )