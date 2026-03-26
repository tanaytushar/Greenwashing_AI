import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Food Risk Analyzer", page_icon="🥗", layout="wide")

st.markdown("""
<style>
.risk-safe            { background:#d4edda; color:#155724; padding:12px 18px; border-radius:8px; font-size:18px; font-weight:bold; }
.risk-moderate        { background:#fff3cd; color:#856404; padding:12px 18px; border-radius:8px; font-size:18px; font-weight:bold; }
.risk-moderatelyhigh  { background:#ffe5b4; color:#7d4000; padding:12px 18px; border-radius:8px; font-size:18px; font-weight:bold; }
.risk-hazardous       { background:#f8d7da; color:#721c24; padding:12px 18px; border-radius:8px; font-size:18px; font-weight:bold; }
.gw-none     { background:#d4edda; color:#155724; padding:10px 16px; border-radius:8px; font-weight:bold; }
.gw-low      { background:#fff3cd; color:#856404; padding:10px 16px; border-radius:8px; font-weight:bold; }
.gw-moderate { background:#ffe5b4; color:#7d4000; padding:10px 16px; border-radius:8px; font-weight:bold; }
.gw-high     { background:#f8d7da; color:#721c24; padding:10px 16px; border-radius:8px; font-weight:bold; }
.meta-box    { background:#1e1e2e; border:1px solid #333; border-radius:10px; padding:16px 20px; margin-bottom:16px; }
.meta-row    { display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #2a2a3a; font-size:14px; }
.meta-key    { color:#888; min-width:160px; }
.meta-val    { color:#eee; font-weight:500; text-align:right; }
.grade-a     { background:#28a745; color:white; padding:2px 10px; border-radius:12px; font-weight:bold; }
.grade-b     { background:#85c341; color:white; padding:2px 10px; border-radius:12px; font-weight:bold; }
.grade-c     { background:#ffc107; color:#333; padding:2px 10px; border-radius:12px; font-weight:bold; }
.grade-d     { background:#fd7e14; color:white; padding:2px 10px; border-radius:12px; font-weight:bold; }
.grade-e     { background:#dc3545; color:white; padding:2px 10px; border-radius:12px; font-weight:bold; }
.badge-safe           { background:#28a745; color:white; padding:2px 10px; border-radius:12px; font-size:12px; }
.badge-moderate       { background:#ffc107; color:#333; padding:2px 10px; border-radius:12px; font-size:12px; }
.badge-moderatelyhigh { background:#fd7e14; color:white; padding:2px 10px; border-radius:12px; font-size:12px; }
.badge-hazardous      { background:#dc3545; color:white; padding:2px 10px; border-radius:12px; font-size:12px; }
.ingredient-row { padding:6px 0; border-bottom:1px solid #2a2a3a; }
.red-flag { color:#dc3545; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

st.title("🥗 Food Ingredient Risk Analyzer")
st.markdown("Paste any product's ingredient list for an instant risk breakdown and greenwashing check.")

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in [
    ("tab1_name", ""), ("tab1_ings", ""),
    ("tab2_name", ""), ("tab2_mkt",  ""), ("tab2_ings", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Grade badge helper ────────────────────────────────────────────────────────
def grade_badge(grade):
    if not grade or str(grade).upper() in ("?", "NONE", "NAN", ""):
        return "<span style='color:#888'>N/A</span>"
    g   = str(grade).upper()
    css = {"A":"grade-a","B":"grade-b","C":"grade-c","D":"grade-d","E":"grade-e"}.get(g,"grade-c")
    return f'<span class="{css}">{g}</span>'

def render_metadata(meta):
    if not meta:
        st.caption("No matching product found in OpenFoodFacts database.")
        return
    st.markdown("#### 📦 Product Metadata (OpenFoodFacts)")
    st.markdown('<div class="meta-box">', unsafe_allow_html=True)
    for key, val in [
        ("Product Name",  meta.get("product_name")),
        ("Generic Name",  meta.get("generic_name")),
        ("Brand",         meta.get("brands")),
        ("Categories",    meta.get("categories")),
        ("Labels / Certs",meta.get("labels_tags")),
        ("Countries",     meta.get("countries_tags")),
    ]:
        display = (val[:80] + "…") if val and len(val) > 80 else (val or "<span style='color:#555'>—</span>")
        st.markdown(
            f'<div class="meta-row"><span class="meta-key">{key}</span>'
            f'<span class="meta-val">{display}</span></div>',
            unsafe_allow_html=True)
    nutri = grade_badge(meta.get("nutriscore_grade"))
    eco_g = grade_badge(meta.get("ecoscore_grade"))
    eco_s = meta.get("ecoscore_score")
    eco_s_str = f"{eco_s:.0f}/100" if eco_s is not None else "N/A"
    st.markdown(
        f'<div class="meta-row"><span class="meta-key">Nutri-Score</span>'
        f'<span class="meta-val">{nutri}</span></div>'
        f'<div class="meta-row"><span class="meta-key">Eco-Score</span>'
        f'<span class="meta-val">{eco_g} &nbsp; {eco_s_str}</span></div>',
        unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🔬 Ingredient Risk Analysis", "🌿 Greenwashing Detector"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Analyze Product Ingredients")

    # ── Quick example buttons (BEFORE widgets so state is set first) ──────────
    examples = {
        "🍫 Chocolate Spread": ("Chocolate Spread",
            "sugar (45%), palm oil (30%), cocoa (15%), milk powder (10%)"),
        "🍜 Instant Noodles":  ("Instant Noodles",
            "wheat flour, palm oil, salt, monosodium glutamate, artificial color"),
        "🥛 Plain Yogurt":     ("Plain Yogurt",
            "milk (95%), live bacterial cultures (5%)"),
        "🧃 Fruit Drink":      ("Fruit Drink",
            "water, high fructose corn syrup, citric acid, artificial flavor, aspartame, sodium benzoate"),
    }

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("**Quick Examples:**")
        ecols = st.columns(2)
        for i, (label, (pname, ings)) in enumerate(examples.items()):
            if ecols[i % 2].button(label, key=f"ex_{i}"):
                st.session_state["tab1_name"] = pname
                st.session_state["tab1_ings"] = ings
                st.rerun()

        product_name = st.text_input("Product Name",
            value=st.session_state["tab1_name"],
            placeholder="e.g. Chocolate Spread", key="t1_pname")
        st.markdown("**Ingredient List**")
        st.caption("Comma-separated, percentages optional")
        ingredients = st.text_area("Ingredients", height=160,
            value=st.session_state["tab1_ings"],
            label_visibility="collapsed",
            placeholder="sugar (45%), palm oil (30%), cocoa (15%)",
            key="t1_ings")
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

    with col2:
        if analyze_btn and ingredients.strip():
            with st.spinner("Analyzing..."):
                try:
                    resp = requests.post(f"{API_URL}/analyze", json={
                        "product_name": product_name or "Product",
                        "ingredients":  ingredients,
                    })
                    data = resp.json()
                    if resp.status_code != 200:
                        st.error(data.get("detail", "API error"))
                    else:
                        tier     = data["risk_tier"]
                        score    = data["risk_score"]
                        tier_key = tier.lower().replace(" ", "")
                        EMOJI    = {"SAFE":"🟢","MODERATE":"🟡","MODERATELY HIGH":"🟠","HAZARDOUS":"🔴"}
                        st.markdown(
                            f'<div class="risk-{tier_key}">{EMOJI.get(tier,"⚪")} {tier} — Risk Score: {score} / 10</div>',
                            unsafe_allow_html=True)
                        if data["red_flags"]:
                            st.markdown("🚩 **Red Flags:** " + ", ".join(f"`{f}`" for f in data["red_flags"]))
                        st.markdown(f"**High-risk ingredients:** {data['high_risk_count']}")
                        st.divider()
                        render_metadata(data.get("metadata"))
                        st.divider()
                        st.markdown("#### Ingredient Breakdown")
                        BADGE = {"safe":"badge-safe","moderate":"badge-moderate",
                                 "moderately high":"badge-moderatelyhigh","hazardous":"badge-hazardous"}
                        for ing in data["ingredients"]:
                            bc  = BADGE.get(ing["label"], "badge-moderate")
                            pct = f" ({ing['percent']}%)" if ing["percent"] else ""
                            flg = ' <span class="red-flag">🚩</span>' if ing["red_flag"] else ""
                            st.markdown(
                                f'<div class="ingredient-row">'
                                f'<span class="{bc}">{ing["label"].upper()}</span> '
                                f'&nbsp;<strong>{ing["ingredient"]}</strong>{pct}{flg}'
                                f'&nbsp;<small style="color:#888">conf: {ing["confidence"]:.0%}</small>'
                                f'</div>', unsafe_allow_html=True)
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to API. Make sure api.py is running.")
        elif analyze_btn:
            st.warning("Please enter an ingredient list.")
        else:
            st.info("👈 Enter a product and ingredients, then click Analyze.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Greenwashing Detector")

    gw_examples = {
        "🍫 Greenwashed Spread": (
            "Chocolate Spread",
            "Our eco-friendly healthy spread is made with natural ingredients. A pure, clean treat.",
            "sugar (45%), palm oil (30%), cocoa (15%), artificial flavor, carrageenan"),
        "🍜 Misleading Noodles": (
            "Instant Noodles",
            "Simple, wholesome noodles. No artificial ingredients. Preservative-free.",
            "wheat flour, palm oil, salt, monosodium glutamate, artificial color, sodium benzoate"),
        "🥛 Honest Yogurt": (
            "Plain Yogurt",
            "Just milk and live cultures. Pure and simple.",
            "milk (95%), live bacterial cultures (5%)"),
    }

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("**Quick Examples:**")
        for i, (label, (pname, mkt, ings)) in enumerate(gw_examples.items()):
            if st.button(label, key=f"gwex_{i}"):
                st.session_state["tab2_name"] = pname
                st.session_state["tab2_mkt"]  = mkt
                st.session_state["tab2_ings"] = ings
                st.rerun()

        gw_product    = st.text_input("Product Name",
            value=st.session_state["tab2_name"],
            placeholder="e.g. Chocolate Spread", key="t2_pname")
        gw_marketing  = st.text_area("Marketing Text", height=110,
            value=st.session_state["tab2_mkt"],
            placeholder="Our eco-friendly healthy spread made with natural pure ingredients.",
            key="t2_mkt")
        gw_ingredients = st.text_area("Ingredient List", height=110,
            value=st.session_state["tab2_ings"],
            placeholder="sugar (45%), palm oil (30%), artificial flavor, carrageenan",
            key="t2_ings")
        gw_btn = st.button("🌿 Check Greenwashing", type="primary", use_container_width=True)

    with col2:
        if gw_btn and gw_ingredients.strip() and gw_marketing.strip():
            with st.spinner("Checking..."):
                try:
                    resp = requests.post(f"{API_URL}/greenwash", json={
                        "product_name":   gw_product or "Product",
                        "marketing_text": gw_marketing,
                        "ingredients":    gw_ingredients,
                    })
                    data = resp.json()
                    if resp.status_code != 200:
                        st.error(data.get("detail", "API error"))
                    else:
                        gw_score = data["gw_score"]
                        gw_tier  = data["gw_tier"]
                        GW_EMOJI = {"NONE":"🟢","LOW":"🟡","MODERATE":"🟠","HIGH":"🔴"}
                        st.markdown(
                            f'<div class="gw-{gw_tier.lower()}">'
                            f'{GW_EMOJI.get(gw_tier,"⚪")} Greenwashing Risk: {gw_tier} — Score: {gw_score} / 10'
                            f'</div>', unsafe_allow_html=True)
                        st.divider()
                        risk = data.get("risk_analysis") or {}
                        render_metadata(risk.get("metadata"))
                        st.divider()
                        claims = data["claims"]
                        st.markdown(f"#### 📣 Marketing Claims ({len(claims)})")
                        if claims:
                            for c in claims:
                                stars = "★" * c["strength"] + "☆" * (3 - c["strength"])
                                st.markdown(f"- **{c['term']}** `{stars}` — *\"{c['sentence']}\"*")
                        else:
                            st.success("No green marketing claims detected.")
                        contradictions = data["contradictions"]
                        st.markdown(f"#### ⚡ Contradictions ({len(contradictions)})")
                        if contradictions:
                            for c in contradictions:
                                st.error(f"Claims **\"{c['claim']}\"** but contains: `{c['ingredient']}`")
                        else:
                            st.success("No contradictions found.")
                        if risk:
                            st.divider()
                            st.markdown("#### 🔬 Ingredient Risk Summary")
                            EMOJI = {"SAFE":"🟢","MODERATE":"🟡","MODERATELY HIGH":"🟠","HAZARDOUS":"🔴"}
                            st.markdown(
                                f"{EMOJI.get(risk['risk_tier'],'⚪')} **{risk['risk_tier']}** "
                                f"— Risk Score: **{risk['risk_score']}**")
                            BADGE = {"safe":"badge-safe","moderate":"badge-moderate",
                                     "moderately high":"badge-moderatelyhigh","hazardous":"badge-hazardous"}
                            for ing in risk.get("ingredients", []):
                                bc  = BADGE.get(ing["label"], "badge-moderate")
                                pct = f" ({ing['percent']}%)" if ing["percent"] else ""
                                flg = ' <span class="red-flag">🚩</span>' if ing["red_flag"] else ""
                                st.markdown(
                                    f'<div class="ingredient-row">'
                                    f'<span class="{bc}">{ing["label"].upper()}</span> '
                                    f'&nbsp;<strong>{ing["ingredient"]}</strong>{pct}{flg}'
                                    f'</div>', unsafe_allow_html=True)
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to API. Make sure api.py is running.")
        elif gw_btn:
            st.warning("Please fill in both marketing text and ingredient list.")
        else:
            st.info("👈 Fill in the product details and click Check Greenwashing.")