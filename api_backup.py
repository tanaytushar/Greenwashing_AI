from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle
import re
import os
import sys
import numpy as np
import pandas as pd
from scipy.sparse import hstack

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enumber_synonyms import normalize_enumbers

# ── Load model artefacts ──────────────────────────────────────────────────────
try:
    model            = pickle.load(open("harm_model.pkl",       "rb"))
    word_vectorizer  = pickle.load(open("word_vectorizer.pkl",  "rb"))
    char_vectorizer  = pickle.load(open("char_vectorizer.pkl",  "rb"))
    le               = pickle.load(open("label_encoder.pkl",    "rb"))
except FileNotFoundError as e:
    raise RuntimeError(f"Model file missing: {e}. Run train_model.py first.")

# ── Load product metadata ─────────────────────────────────────────────────────
_df_meta = None
if os.path.isfile("products_metadata.csv"):
    print("Loading products_metadata.csv...")
    _df_meta = pd.read_csv("products_metadata.csv", low_memory=False)
    _df_meta["_name_lower"] = (
        _df_meta["product_name"].astype(str).str.lower().str.strip()
    )
    print(f"  Loaded {len(_df_meta):,} product records.")
else:
    print("products_metadata.csv not found — re-run extract_ingredients.py to enable metadata lookup.")


def _clean_val(val):
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    s = str(val).strip()
    return None if s in ("nan", "?", "", "Unknown") else s


def lookup_metadata(product_name: str):
    if _df_meta is None:
        return None
    query   = product_name.lower().strip()
    matches = _df_meta[_df_meta["_name_lower"] == query]
    if matches.empty:
        matches = _df_meta[_df_meta["_name_lower"].str.contains(
            re.escape(query), na=False)]
    if matches.empty:
        return None
    row = matches.iloc[0]
    eco_score = row.get("ecoscore_score")
    return {
        "product_name":     _clean_val(row.get("product_name")),
        "generic_name":     _clean_val(row.get("generic_name")),
        "brands":           _clean_val(row.get("brands")),
        "categories":       _clean_val(row.get("categories")),
        "labels_tags":      _clean_val(row.get("labels_tags")),
        "ecoscore_grade":   _clean_val(row.get("ecoscore_grade")),
        "ecoscore_score":   None if (isinstance(eco_score, float) and np.isnan(eco_score)) else eco_score,
        "nutriscore_grade": _clean_val(row.get("nutriscore_grade")),
        "countries_tags":   _clean_val(row.get("countries_tags")),
    }


# ── Constants ─────────────────────────────────────────────────────────────────
SEVERITY_SCORE = {
    "safe":            1,
    "moderate":        2,
    "moderately high": 4,
    "hazardous":       7,
}

CONFIDENCE_THRESHOLD  = 0.50
MAX_INGREDIENT_WEIGHT = 0.40

RED_FLAG_INGREDIENTS = [
    "titanium dioxide", "bha", "bht", "tbhq",
    "partially hydrogenated", "hydrogenated",
    "sodium nitrite", "potassium nitrate", "nitrite", "nitrate",
    "potassium bromate", "brominated vegetable oil",
    "artificial color", "caramel color", "aspartame", "propylene glycol",
]

GREEN_TERMS = {
    "green": 1, "eco": 1, "planet": 1, "responsible": 1,
    "sustainable": 2, "clean": 2, "pure": 2, "wholesome": 2,
    "natural": 3, "organic": 3, "healthy": 3, "nutritious": 3,
    "additive-free": 3, "preservative-free": 3,
    "no artificial": 3, "no added sugar": 3, "sugar-free": 3,
}

CONTRADICTIONS = {
    "natural":      [r"artificial", r"hydrogenated", r"titanium dioxide",
                     r"\bbha\b", r"\bbht\b", r"polysorbate", r"carrageenan"],
    "organic":      [r"artificial", r"hydrogenated", r"\bbha\b",
                     r"titanium dioxide", r"maltodextrin"],
    "healthy":      [r"high fructose corn syrup", r"hydrogenated",
                     r"nitrite", r"nitrate", r"\bbha\b", r"artificial color"],
    "clean":        [r"artificial", r"hydrogenated", r"\bbha\b",
                     r"titanium dioxide", r"carrageenan"],
    "preservative-free": [r"benzoate", r"sorbate", r"nitrite",
                           r"\bbha\b", r"\bbht\b"],
    "no artificial":  [r"artificial color", r"artificial flavor"],
    "no added sugar": [r"\bsugar\b", r"corn syrup", r"high fructose",
                       r"dextrose", r"maltose"],
    "sugar-free":     [r"\bsugar\b", r"corn syrup", r"high fructose"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def override_label(ingredient: str):
    ing = ingredient.lower()
    if "partially hydrogenated" in ing or "hydrogenated" in ing:
        return "hazardous"
    if "nitrite" in ing or "nitrate" in ing:
        return "hazardous"
    if "titanium dioxide" in ing:
        return "hazardous"
    if any(x in ing for x in ["bha", "bht", "tbhq"]):
        return "hazardous"
    if "aspartame" in ing:
        return "moderately high"
    for term in ["sugar", "sucrose", "fructose", "dextrose",
                 "corn syrup", "maltose", "high fructose"]:
        if term in ing:
            return "moderately high"
    return None

def extract_percentage(raw: str):
    match = re.search(r"\((\d+\.?\d*)\s*%\)", raw)
    return float(match.group(1)) if match else None

def predict_with_confidence(ingredient: str):
    Xw = word_vectorizer.transform([ingredient])
    Xc = char_vectorizer.transform([ingredient])
    X  = hstack([Xw, Xc])
    proba   = model.predict_proba(X)[0]
    idx     = proba.argmax()
    return le.inverse_transform([idx])[0], float(proba[idx])

def is_unknown(ingredient: str, confidence: float) -> bool:
    if confidence < CONFIDENCE_THRESHOLD:
        return True
    tokens = ingredient.split()
    if not tokens:
        return True
    known = sum(1 for t in tokens if t in word_vectorizer.vocabulary_)
    return (known / len(tokens)) < 0.3

def check_red_flags(ingredient: str):
    return [f for f in RED_FLAG_INGREDIENTS if f in ingredient.lower()]

def run_product_analysis(product_name: str, ingredient_text: str):
    raw_ingredients = [i.strip() for i in ingredient_text.split(",")]
    total_score = total_weight = 0.0
    high_risk_count = 0
    red_flags_found = []
    results = []

    for idx, raw_ing in enumerate(raw_ingredients):
        if not raw_ing:
            continue
        percent    = extract_percentage(raw_ing)
        ingredient = re.sub(r"\(\d+\.?\d*\s*%\)", "", raw_ing).strip().lower()
        ingredient = normalize_enumbers(ingredient)

        weight = min(
            (percent / 100.0) if percent is not None else 1.0 / (idx + 1),
            MAX_INGREDIENT_WEIGHT
        )

        flags  = check_red_flags(ingredient)
        forced = override_label(ingredient)

        if forced:
            label, confidence, method = forced, 1.0, "override"
        else:
            ml_label, confidence = predict_with_confidence(ingredient)
            if is_unknown(ingredient, confidence):
                label, method = "moderate", "unknown-fallback"
            else:
                label, method = ml_label, "model"

        severity = SEVERITY_SCORE.get(label, 2)
        if label in ("moderately high", "hazardous"):
            high_risk_count += 1

        red_flags_found.extend(flags)
        total_score  += severity * weight
        total_weight += weight

        results.append({
            "ingredient": ingredient,
            "percent":    percent,
            "label":      label,
            "confidence": round(confidence, 2),
            "method":     method,
            "red_flag":   bool(flags),
        })

    if total_weight == 0:
        return None

    avg_score = total_score / total_weight
    if high_risk_count >= 3:
        avg_score += 1.5
    elif high_risk_count >= 2:
        avg_score += 1.0
    if red_flags_found:
        avg_score += 0.5

    if avg_score < 1.4:
        tier = "SAFE"
    elif avg_score < 2.3:
        tier = "MODERATE"
    elif avg_score < 3.3:
        tier = "MODERATELY HIGH"
    else:
        tier = "HAZARDOUS"

    # ── Attach OpenFoodFacts metadata if available ────────────────────────────
    metadata = lookup_metadata(product_name)

    return {
        "product":          product_name,
        "metadata":         metadata,        # ← NEW
        "ingredients":      results,
        "risk_score":       round(avg_score, 2),
        "risk_tier":        tier,
        "high_risk_count":  high_risk_count,
        "red_flags":        list(dict.fromkeys(red_flags_found)),
    }

def run_greenwashing_analysis(product_name: str,
                              marketing_text: str,
                              ingredient_text: str):
    ingredients_norm = normalize_enumbers(ingredient_text.lower())
    sentences = re.split(r"[.!?\n]", marketing_text.lower())
    claims = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for term, strength in GREEN_TERMS.items():
            if re.search(r'\b' + re.escape(term) + r'\b', sentence):
                claims.append({"term": term, "sentence": sentence,
                                "strength": strength})

    contradictions = []
    for claim in claims:
        term = claim["term"]
        if term not in CONTRADICTIONS:
            continue
        for pattern in CONTRADICTIONS[term]:
            if re.search(pattern, ingredients_norm):
                contradictions.append({
                    "claim":      term,
                    "strength":   claim["strength"],
                    "ingredient": pattern.replace(r"\b", "").strip(),
                })

    gw_score = min(
        round(
            sum(c["strength"] * 1.5 for c in claims) +
            sum(c["strength"] * 2.5 for c in contradictions), 1
        ), 10.0
    )

    if gw_score == 0:        gw_tier = "NONE"
    elif gw_score < 3:       gw_tier = "LOW"
    elif gw_score < 6:       gw_tier = "MODERATE"
    else:                    gw_tier = "HIGH"

    risk = run_product_analysis(product_name, ingredient_text)

    return {
        "product":        product_name,
        "claims":         claims,
        "contradictions": contradictions,
        "gw_score":       gw_score,
        "gw_tier":        gw_tier,
        "risk_analysis":  risk,
    }


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Food Ingredient Risk Analyzer API",
    description="Analyzes food ingredients for health risk and greenwashing.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    product_name: str
    ingredients:  str

class GreenwashRequest(BaseModel):
    product_name:   str
    marketing_text: str
    ingredients:    str

@app.get("/")
def root():
    return {"message": "Food Risk Analyzer API v2 is running."}

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    result = run_product_analysis(req.product_name, req.ingredients)
    if result is None:
        raise HTTPException(status_code=400, detail="No valid ingredients found.")
    return result

@app.post("/greenwash")
def greenwash(req: GreenwashRequest):
    return run_greenwashing_analysis(
        req.product_name, req.marketing_text, req.ingredients)

@app.get("/health")
def health():
    return {"status": "ok", "metadata_loaded": _df_meta is not None}