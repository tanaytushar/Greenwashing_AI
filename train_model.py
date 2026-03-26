import pandas as pd
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import pickle
import os

print("Loading dataset...")

df = pd.read_csv("labeled_ingredients.csv")

# ── Clean ─────────────────────────────────────────────────────────────────────
df = df.dropna(subset=["ingredient", "harm_level"])
df["ingredient"] = df["ingredient"].astype(str).str.strip()

print(f"Dataset size: {len(df)} rows")
print("\nLabel distribution:")
print(df["harm_level"].value_counts())

# ── Encode labels ─────────────────────────────────────────────────────────────
le = LabelEncoder()
df["label"] = le.fit_transform(df["harm_level"])
print("\nClasses:", list(le.classes_))

# ── Feature engineering ───────────────────────────────────────────────────────
# Vectorizer 1: word unigrams + bigrams (semantic meaning)
word_vectorizer = TfidfVectorizer(
    analyzer="word",
    ngram_range=(1, 2),
    min_df=2,          # ignore terms appearing in fewer than 2 docs
    sublinear_tf=True  # apply log normalization to term frequencies
)

# Vectorizer 2: character n-grams (catch suffixes like "-ose", "-ate", "-ite")
# These are chemically meaningful: glucose/fructose/maltose all end in "-ose"
# and share metabolic risk; nitrite/nitrate share "-ite"/"-ate" endings.
char_vectorizer = TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(3, 5),
    min_df=2,
    sublinear_tf=True
)

print("\nFitting vectorizers...")
X_word = word_vectorizer.fit_transform(df["ingredient"])
X_char = char_vectorizer.fit_transform(df["ingredient"])

# Stack both feature matrices horizontally
X = hstack([X_word, X_char])
y = df["label"].values

print(f"Feature matrix shape: {X.shape}")

# ── Train / test split ────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# ── Model ─────────────────────────────────────────────────────────────────────
print("\nTraining RandomForest model...")

model = RandomForestClassifier(
    n_estimators=400,
    max_depth=None,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1          # use all CPU cores
)

model.fit(X_train, y_train)

# ── Evaluation ────────────────────────────────────────────────────────────────
print("\n── Test Set Results ──")
y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred, target_names=le.classes_))

print("\n── Confusion Matrix ──")
cm = confusion_matrix(y_test, y_pred)
cm_df = pd.DataFrame(cm, index=le.classes_, columns=le.classes_)
print(cm_df)

# ── Cross-validation (5-fold) — overall model robustness check ───────────────
# NOTE: CV on auto-labeled data measures consistency, not ground-truth accuracy.
# Replace with manually-verified labels when available for a meaningful score.
print("\n── 5-Fold Cross-Validation (macro F1) ──")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=cv, scoring="f1_macro", n_jobs=-1)
print(f"Mean: {cv_scores.mean():.4f}  Std: {cv_scores.std():.4f}")
print(f"Per-fold: {[round(s, 4) for s in cv_scores]}")

# ── Confidence calibration check ─────────────────────────────────────────────
# Shows average confidence per predicted class on test set.
# Low average confidence on a class = model is uncertain → watch for those.
proba = model.predict_proba(X_test)
max_proba = proba.max(axis=1)
print("\n── Prediction Confidence on Test Set ──")
print(f"Mean confidence : {max_proba.mean():.4f}")
print(f"% predictions with confidence < 0.5 : "
      f"{(max_proba < 0.5).mean() * 100:.1f}%  (these trigger unknown fallback)")
print(f"% predictions with confidence < 0.7 : "
      f"{(max_proba < 0.7).mean() * 100:.1f}%")

# ── Save artefacts ────────────────────────────────────────────────────────────
print("\nSaving model files...")

pickle.dump(model,          open("harm_model.pkl",      "wb"))
pickle.dump(word_vectorizer, open("word_vectorizer.pkl", "wb"))
pickle.dump(char_vectorizer, open("char_vectorizer.pkl", "wb"))
pickle.dump(le,             open("label_encoder.pkl",   "wb"))

# Also save vocabulary size for diagnostics in product_risk.py
meta = {
    "word_vocab_size": len(word_vectorizer.vocabulary_),
    "char_vocab_size": len(char_vectorizer.vocabulary_),
    "classes": list(le.classes_),
    "cv_f1_mean": round(float(cv_scores.mean()), 4),
}
import json
with open("model_meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print("\n✅ 4-class model trained and saved successfully!")
print(f"   Word vocab size : {meta['word_vocab_size']}")
print(f"   Char vocab size : {meta['char_vocab_size']}")
print(f"   CV macro-F1     : {meta['cv_f1_mean']}")