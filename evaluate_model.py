import pandas as pd
import numpy as np
import pickle
import json
from scipy.sparse import hstack
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
import matplotlib.pyplot as plt
import seaborn as sns
import os

print("=" * 60)
print("   MODEL EVALUATION REPORT")
print("=" * 60)

# ── Load model ────────────────────────────────────────────────────────────────
model           = pickle.load(open("harm_model.pkl",      "rb"))
word_vectorizer = pickle.load(open("word_vectorizer.pkl", "rb"))
char_vectorizer = pickle.load(open("char_vectorizer.pkl", "rb"))
le              = pickle.load(open("label_encoder.pkl",   "rb"))

print(f"\nClasses: {list(le.classes_)}")

# ── Load dataset ──────────────────────────────────────────────────────────────
df = pd.read_csv("labeled_ingredients.csv")
df = df.dropna(subset=["ingredient", "harm_level"])
df["ingredient"] = df["ingredient"].astype(str).str.strip()

print(f"Total samples: {len(df)}")
print("\nClass distribution:")
dist = df["harm_level"].value_counts()
for cls, count in dist.items():
    pct = count / len(df) * 100
    print(f"  {cls:<20} {count:>5}  ({pct:.1f}%)")

# ── Build features ────────────────────────────────────────────────────────────
X_word = word_vectorizer.transform(df["ingredient"])
X_char = char_vectorizer.transform(df["ingredient"])
X      = hstack([X_word, X_char])
y      = le.transform(df["harm_level"])

# ── Train/test split (same seed as training) ──────────────────────────────────
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

y_pred  = model.predict(X_test)
y_proba = model.predict_proba(X_test)

# ── 1. Overall Accuracy ───────────────────────────────────────────────────────
acc = accuracy_score(y_test, y_pred)
print(f"\n{'─'*60}")
print(f"  Overall Accuracy     : {acc*100:.2f}%")
print(f"  Macro F1 Score       : {f1_score(y_test, y_pred, average='macro')*100:.2f}%")
print(f"  Weighted F1 Score    : {f1_score(y_test, y_pred, average='weighted')*100:.2f}%")
print(f"  Macro Precision      : {precision_score(y_test, y_pred, average='macro')*100:.2f}%")
print(f"  Macro Recall         : {recall_score(y_test, y_pred, average='macro')*100:.2f}%")

# ── 2. Per-class Report ───────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print("  Per-Class Report:")
print(f"{'─'*60}")
report = classification_report(
    y_test, y_pred,
    target_names=le.classes_,
    digits=3
)
print(report)

# ── 3. Confusion Matrix ───────────────────────────────────────────────────────
cm = confusion_matrix(y_test, y_pred)
cm_df = pd.DataFrame(cm, index=le.classes_, columns=le.classes_)
print(f"{'─'*60}")
print("  Confusion Matrix (rows=actual, cols=predicted):")
print(f"{'─'*60}")
print(cm_df.to_string())

# ── 4. Confidence Analysis ────────────────────────────────────────────────────
max_proba = y_proba.max(axis=1)
print(f"\n{'─'*60}")
print("  Prediction Confidence Distribution:")
print(f"{'─'*60}")
print(f"  Mean confidence       : {max_proba.mean()*100:.1f}%")
print(f"  Median confidence     : {np.median(max_proba)*100:.1f}%")
print(f"  Low confidence (<50%) : {(max_proba < 0.50).sum()} predictions "
      f"({(max_proba < 0.50).mean()*100:.1f}%)")
print(f"  Low confidence (<70%) : {(max_proba < 0.70).sum()} predictions "
      f"({(max_proba < 0.70).mean()*100:.1f}%)")
print(f"  High confidence (>90%): {(max_proba > 0.90).sum()} predictions "
      f"({(max_proba > 0.90).mean()*100:.1f}%)")

# ── 5. Cross-Validation ───────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print("  5-Fold Cross-Validation:")
print(f"{'─'*60}")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
for metric in ["accuracy", "f1_macro"]:
    scores = cross_val_score(model, X, y, cv=cv, scoring=metric, n_jobs=-1)
    print(f"  {metric:<20} Mean: {scores.mean()*100:.2f}%  "
          f"Std: {scores.std()*100:.2f}%  "
          f"Min: {scores.min()*100:.2f}%  "
          f"Max: {scores.max()*100:.2f}%")

# ── 6. Most Confused Pairs ────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print("  Most Common Misclassifications:")
print(f"{'─'*60}")
wrong_idx  = np.where(y_pred != y_test)[0]
wrong_df   = pd.DataFrame({
    "ingredient": df.iloc[
        df.index[
            pd.RangeIndex(len(df))
            [int(X_train.shape[0]):]
        ]
    ]["ingredient"].values,
    "actual":    le.inverse_transform(y_test),
    "predicted": le.inverse_transform(y_pred),
    "confidence": max_proba,
})
wrong_only = wrong_df[wrong_df["actual"] != wrong_df["predicted"]]
pair_counts = wrong_only.groupby(["actual","predicted"]).size().reset_index(name="count")
pair_counts = pair_counts.sort_values("count", ascending=False).head(10)
print(pair_counts.to_string(index=False))

print(f"\n  Total misclassified: {len(wrong_only)} / {len(y_test)} "
      f"({len(wrong_only)/len(y_test)*100:.1f}%)")

# ── 7. Sample wrong predictions ───────────────────────────────────────────────
print(f"\n{'─'*60}")
print("  Sample Wrong Predictions (low confidence):")
print(f"{'─'*60}")
worst = wrong_only.sort_values("confidence").head(15)
for _, row in worst.iterrows():
    print(f"  '{row['ingredient']}'"
          f"\n    actual={row['actual']}  predicted={row['predicted']}"
          f"  conf={row['confidence']:.2f}\n")

# ── 8. Save plots ─────────────────────────────────────────────────────────────
try:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Confusion matrix heatmap
    sns.heatmap(
        cm_df, annot=True, fmt="d", cmap="Blues",
        ax=axes[0], linewidths=0.5
    )
    axes[0].set_title("Confusion Matrix", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Actual")
    axes[0].set_xlabel("Predicted")

    # Confidence histogram
    axes[1].hist(max_proba, bins=20, color="#4e79a7", edgecolor="white")
    axes[1].axvline(0.5, color="red",    linestyle="--", label="50% threshold")
    axes[1].axvline(0.7, color="orange", linestyle="--", label="70% threshold")
    axes[1].set_title("Prediction Confidence Distribution", fontsize=13, fontweight="bold")
    axes[1].set_xlabel("Confidence")
    axes[1].set_ylabel("Count")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig("model_evaluation.png", dpi=150, bbox_inches="tight")
    print(f"\n✅ Evaluation plot saved → model_evaluation.png")

except Exception as e:
    print(f"\n⚠  Could not save plot: {e}")
    print("   Run: pip install matplotlib seaborn")

# ── 9. Save summary JSON ──────────────────────────────────────────────────────
summary = {
    "total_samples":    len(df),
    "test_samples":     len(y_test),
    "overall_accuracy": round(acc * 100, 2),
    "macro_f1":         round(f1_score(y_test, y_pred, average="macro") * 100, 2),
    "weighted_f1":      round(f1_score(y_test, y_pred, average="weighted") * 100, 2),
    "mean_confidence":  round(float(max_proba.mean()) * 100, 2),
    "low_conf_pct":     round(float((max_proba < 0.5).mean()) * 100, 2),
    "misclassified_pct":round(len(wrong_only) / len(y_test) * 100, 2),
    "classes":          list(le.classes_),
}
with open("model_evaluation_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"✅ Summary saved → model_evaluation_summary.json")
print(f"\n{'='*60}")
print(f"  FINAL VERDICT")
print(f"{'='*60}")
if acc >= 0.90:
    print(f"  🟢 EXCELLENT — {acc*100:.1f}% accuracy. Model is production-ready.")
elif acc >= 0.80:
    print(f"  🟡 GOOD — {acc*100:.1f}% accuracy. Works well, room to improve.")
elif acc >= 0.70:
    print(f"  🟠 FAIR — {acc*100:.1f}% accuracy. Consider more training data.")
else:
    print(f"  🔴 POOR — {acc*100:.1f}% accuracy. Model needs significant improvement.")
print(f"{'='*60}\n")
