import pandas as pd
from collections import Counter
import re

url = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
ingredient_counter = Counter()
chunk_size = 50000

print(f"Downloading and streaming from {url} ...")

try:
    for chunk in pd.read_csv(
        url,
        sep="\t",
        usecols=["ingredients_text"],
        chunksize=chunk_size,
        low_memory=False,
        compression="gzip",
        on_bad_lines='skip'
    ):
        chunk = chunk.dropna()
        for text in chunk["ingredients_text"]:
            parts = re.split(r',|;|\(|\)', str(text).lower())
            for p in parts:
                item = p.strip()
                if len(item) > 2:
                    ingredient_counter[item] += 1
                    
        print(f"Processed chunk... (Current top ingredients: {len(ingredient_counter)})")
        
        # To avoid taking hours, process a representative sample, e.g., ~500,000 products
        if sum(ingredient_counter.values()) > 5000000:
            print("Reached a representative sample size, halting stream early.")
            break

except Exception as e:
    print(f"Streaming interrupted: {e}")

print("Finished processing stream.")

# Get top 5000 ingredients
top_5000 = ingredient_counter.most_common(5000)
df_top = pd.DataFrame(top_5000, columns=["ingredient", "frequency"])
df_top.to_csv("top_5000ingredients.csv", index=False)

print("✅ Saved top 5000 ingredients to top_5000ingredients.csv")