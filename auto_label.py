import pandas as pd
import re

print("Loading ingredients...")

df = pd.read_csv("cleaned_ingredients.csv")
df = df.dropna(subset=["ingredient"])
df["ingredient"] = df["ingredient"].str.lower().str.strip()

# ==============================
# HAZARDOUS (Strong Evidence Risk)
# ==============================

HAZARDOUS_PATTERNS = [
    r"\bbha\b",
    r"\bbht\b",
    r"\btbhq\b",
    r"\btitanium dioxide\b",
    r"\bnitrite\b",
    r"\bnitrate\b",
    r"\bpropylene glycol\b",
    r"\bcalcium disodium edta\b",
    r"\bpartially hydrogenated\b",
    r"\bhydrogenated\b",
    r"\bartificial color\b",
    r"\bcaramel color\b",
]

# ==============================
# MODERATELY HIGH (Metabolic / Additive Risk)
# ==============================

MODERATELY_HIGH_PATTERNS = [
    r"\bartificial flavor\b",
    r"\bmonosodium glutamate\b",
    r"\bmsg\b",
    r"\bdisodium inosinate\b",
    r"\bdisodium guanylate\b",
    r"\bphosphate\b",
    r"\bcarrageenan\b",
    r"\bmaltodextrin\b",
    r"\bcorn syrup\b",
    r"\bhigh fructose corn syrup\b",
    r"\bsugar\b",
    r"\bglucose\b",
    r"\bfructose\b",
    r"\baspartame\b",
    r"\bsucralose\b",
    r"\bacesulfame\b",
    r"\bpolysorbate\b",
    r"\bpreservative\b",
    r"\bsweetener\b",
]

# ==============================
# MODERATE (Processing / Refinement)
# ==============================

MODERATE_PATTERNS = [
    r"\boil\b",
    r"\bstarch\b",
    r"\bgum\b",
    r"\blecithin\b",
    r"\bemulsifier\b",
    r"\bflavor\b",
    r"\bflavour\b",
    r"\bextract\b",
    r"\bcarbonate\b",
    r"\blactic acid\b",
    r"\bcitric acid\b",
    r"\bacidity regulator\b",
    r"\bmodified\b",
]

# ==============================
# SAFE (Whole / Natural Foods)
# ==============================

SAFE_PATTERNS = [
    r"\bwater\b",
    r"\bmilk\b",
    r"\begg\b",
    r"\bflour\b",
    r"\bwheat\b",
    r"\brice\b",
    r"\bhoney\b",
    r"\bbutter\b",
    r"\bgarlic\b",
    r"\bonion\b",
    r"\bpepper\b",
    r"\bturmeric\b",
    r"\btomato\b",
    r"\bpotato\b",
    r"\balmond\b",
    r"\bpeanut\b",
    r"\bcheese\b",
    r"\bcream\b",
    r"\bsalt\b",
    r"\bfruit\b",
    r"\bbeef\b",
    r"\bchicken\b",
    r"\bpork\b",
    r"\bherb\b",
    r"\bspice\b",
]

from ground_truth_mapper import get_ground_truth

def classify(ingredient):
    # 1. Check ground truth / FDA exact mappings + E-numbers
    ground_truth_label = get_ground_truth(ingredient)
    if ground_truth_label:
        return ground_truth_label

    # 2. Fall back to regex patterns
    for pattern in HAZARDOUS_PATTERNS:
        if re.search(pattern, ingredient):
            return "hazardous"

    for pattern in MODERATELY_HIGH_PATTERNS:
        if re.search(pattern, ingredient):
            return "moderately high"

    for pattern in MODERATE_PATTERNS:
        if re.search(pattern, ingredient):
            return "moderate"

    for pattern in SAFE_PATTERNS:
        if re.search(pattern, ingredient):
            return "safe"

    return "moderate"  # conservative fallback


print("Applying 4-class classification...")

df["harm_level"] = df["ingredient"].apply(classify)

print("\nFinal Distribution:")
print(df["harm_level"].value_counts())

df.to_csv("labeled_ingredients.csv", index=False)

print("\n✅ 4-Class labeling complete.")