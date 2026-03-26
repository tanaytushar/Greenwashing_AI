import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from product_risk import analyze_product
from enumber_synonyms import normalize_enumbers

# ── Green marketing claim vocabulary ─────────────────────────────────────────
# Each term is paired with a "strength" score (1–3):
#   1 = vague puffery (nearly unfalsifiable)
#   2 = moderate claim (partially verifiable)
#   3 = strong claim (objectively testable against ingredients)

GREEN_TERMS = {
    # Strength 1 — vague
    "green":        1,
    "eco":          1,
    "planet":       1,
    "earth":        1,
    "responsible":  1,
    "ethical":      1,
    "conscious":    1,
    # Strength 2 — moderate
    "sustainable":  2,
    "clean":        2,
    "pure":         2,
    "wholesome":    2,
    "real":         2,
    "honest":       2,
    "simple":       2,
    # Strength 3 — strong (directly contradicted by certain ingredients)
    "natural":      3,
    "organic":      3,
    "healthy":      3,
    "nutritious":   3,
    "additive-free": 3,
    "preservative-free": 3,
    "no artificial": 3,
    "no added sugar": 3,
    "sugar-free":   3,
}

# ── Ingredient patterns that directly contradict green claims ─────────────────
# Maps claim keywords to the ingredient patterns they clash with.
CONTRADICTIONS = {
    "natural":      [r"artificial", r"synthetic", r"hydrogenated",
                     r"titanium dioxide", r"\bbha\b", r"\bbht\b",
                     r"polysorbate", r"carrageenan"],
    "organic":      [r"artificial", r"hydrogenated", r"\bbha\b", r"\bbht\b",
                     r"titanium dioxide", r"phosphate", r"maltodextrin"],
    "healthy":      [r"high fructose corn syrup", r"hydrogenated", r"nitrite",
                     r"nitrate", r"\bbha\b", r"\bbht\b", r"artificial color",
                     r"sucralose", r"aspartame"],
    "nutritious":   [r"high fructose corn syrup", r"maltodextrin",
                     r"artificial flavor", r"carrageenan"],
    "additive-free": [r"polysorbate", r"carrageenan", r"phosphate",
                      r"\bgum\b", r"emulsifier", r"lecithin"],
    "preservative-free": [r"benzoate", r"sorbate", r"nitrite", r"nitrate",
                          r"\bbha\b", r"\bbht\b", r"sulphite", r"sulfite"],
    "no artificial": [r"artificial color", r"artificial flavor",
                      r"artificial sweetener"],
    "no added sugar": [r"\bsugar\b", r"corn syrup", r"high fructose",
                       r"dextrose", r"maltose", r"glucose syrup"],
    "sugar-free":   [r"\bsugar\b", r"corn syrup", r"high fructose",
                     r"dextrose", r"maltose"],
    "clean":        [r"artificial", r"hydrogenated", r"\bbha\b", r"\bbht\b",
                     r"titanium dioxide", r"carrageenan"],
    "pure":         [r"artificial", r"hydrogenated", r"polysorbate",
                     r"carrageenan", r"\bbha\b"],
    "simple":       [r"polysorbate", r"carrageenan", r"phosphate",
                     r"disodium", r"calcium disodium edta", r"emulsifier"],
}


def extract_claims(marketing_text: str) -> list[dict]:
    """
    Parse marketing text into a list of claim objects with the sentence
    that contained them and the claim strength score.
    """
    sentences = re.split(r"[.!?\n]", marketing_text.lower())
    claims = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for term, strength in GREEN_TERMS.items():
            if re.search(r'\b' + re.escape(term) + r'\b', sentence):
                claims.append({
                    "term":     term,
                    "sentence": sentence,
                    "strength": strength,
                })

    return claims


def find_contradictions(claims: list[dict], ingredients_lower: str) -> list[dict]:
    """
    For each strong/moderate claim, check whether the ingredient list
    contains substances that contradict it.
    Returns a list of contradiction objects.
    """
    contradictions_found = []

    for claim in claims:
        term = claim["term"]
        if term not in CONTRADICTIONS:
            continue

        for pattern in CONTRADICTIONS[term]:
            if re.search(pattern, ingredients_lower):
                contradictions_found.append({
                    "claim":       term,
                    "strength":    claim["strength"],
                    "sentence":    claim["sentence"],
                    "ingredient":  pattern.replace(r"\b", "").strip(),
                })

    return contradictions_found


def greenwashing_score(claims: list[dict], contradictions: list[dict]) -> float:
    """
    Compute a 0–10 greenwashing risk score.

    Logic:
    - Start at 0.
    - Add claim_strength × 1.5 for each strong claim made.
    - Add claim_strength × 2.5 for each contradiction found
      (making a claim that is directly refuted by ingredients is worse).
    - Cap at 10.
    """
    score = 0.0

    for c in claims:
        score += c["strength"] * 1.5

    for c in contradictions:
        score += c["strength"] * 2.5

    return min(round(score, 1), 10.0)


def detect_greenwashing(product_name: str,
                        marketing_text: str,
                        ingredients: str):
    """
    Full greenwashing analysis pipeline.

    Parameters
    ----------
    product_name   : Display name of the product.
    marketing_text : Raw marketing copy (packaging text, ads, website copy).
    ingredients    : Raw ingredient list string (comma-separated).
    """
    print("\n" + "█" * 55)
    print(f"  GREENWASHING ANALYSIS — {product_name}")
    print("█" * 55)

    # Normalise ingredients for pattern matching
    ingredients_normalised = normalize_enumbers(ingredients.lower())

    # ── Step 1: Extract marketing claims ─────────────────────────────────────
    claims = extract_claims(marketing_text)

    print(f"\n📣  Marketing Claims Found ({len(claims)}):")
    if claims:
        for c in claims:
            stars = "★" * c["strength"] + "☆" * (3 - c["strength"])
            print(f"    [{stars}] \"{c['term']}\"  in:  \"{c['sentence']}\"")
    else:
        print("    None detected.")

    # ── Step 2: Find contradictions ───────────────────────────────────────────
    contradictions = find_contradictions(claims, ingredients_normalised)

    print(f"\n⚡  Claim-vs-Ingredient Contradictions ({len(contradictions)}):")
    if contradictions:
        for c in contradictions:
            print(f"    ✗  Claims \"{c['claim']}\" but contains: {c['ingredient']}")
    else:
        print("    None detected.")

    # ── Step 3: Ingredient risk analysis ─────────────────────────────────────
    print("\n🔬  Running Ingredient Risk Analysis...")
    risk_result = analyze_product(product_name, ingredients)

    # ── Step 4: Greenwashing score ────────────────────────────────────────────
    gw_score = greenwashing_score(claims, contradictions)

    print("\n" + "─" * 55)
    print(f"  Greenwashing Risk Score  : {gw_score} / 10")

    if gw_score == 0:
        print("  🟢 No greenwashing signals detected.")
    elif gw_score < 3:
        print("  🟡 Low greenwashing risk — vague claims only.")
    elif gw_score < 6:
        print("  🟠 Moderate greenwashing risk — "
              "some claims not supported by ingredients.")
    else:
        print("  🔴 HIGH greenwashing risk — "
              "marketing claims directly contradict ingredient list.")

    # ── Step 5: Summary advice ────────────────────────────────────────────────
    if contradictions:
        print("\n  💡 Recommendation:")
        for c in contradictions:
            term = c["claim"]
            ing  = c["ingredient"]
            if term in ("natural", "clean", "pure"):
                print(f"     Remove '{term}' claim OR reformulate to "
                      f"exclude: {ing}")
            elif term in ("no added sugar", "sugar-free"):
                print(f"     Remove '{term}' claim — product contains "
                      f"sugar/syrup ingredients.")
            elif term == "preservative-free":
                print(f"     Remove '{term}' claim — product contains "
                      f"preservatives ({ing}).")
            else:
                print(f"     Substantiate or remove '{term}' claim "
                      f"(contradicted by: {ing}).")

    print("█" * 55)

    return {
        "product":          product_name,
        "claims":           claims,
        "contradictions":   contradictions,
        "gw_score":         gw_score,
        "risk_result":      risk_result,
    }


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    detect_greenwashing(
        "Chocolate Spread",
        "Our eco-friendly healthy spread is made with natural ingredients. "
        "A pure, clean treat for the whole family.",
        "sugar (45%), palm oil (30%), cocoa (15%), milk powder (5%), "
        "artificial flavor, carrageenan"
    )

    detect_greenwashing(
        "Instant Noodles",
        "Simple, wholesome noodles. No artificial ingredients. "
        "Our sustainable, preservative-free recipe.",
        "wheat flour, palm oil, salt, monosodium glutamate, "
        "artificial color, sodium benzoate"
    )

    detect_greenwashing(
        "Plain Yogurt",
        "Just milk and live cultures. Pure and simple.",
        "milk (95%), live bacterial cultures (5%)"
    )