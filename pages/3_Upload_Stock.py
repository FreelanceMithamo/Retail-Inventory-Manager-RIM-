import streamlit as st
import pandas as pd
import db
import utils

st.set_page_config(page_title="Upload Stock • BRIM", page_icon="📤", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("📤 Upload Real-Time Stock")

user = st.session_state.user
if not user:
    st.warning("Please log in first (see the Login page in the sidebar).")
    st.stop()

st.markdown("""
Upload your **current stock snapshot**. Each upload **replaces** your previous
stock list — so upload your full, current stock count each time (e.g. after a
stock take, or as often as daily).

**Only two things are required: a product name and a quantity.** Everything
else is optional:

- **SKU / model / item code** — if you don't have one, we'll use the product name instead.
- **Category / item group** — leave blank if you don't track categories.
- **Unit cost** — leave blank entirely (or drop the column) if you'd rather focus purely
  on quantities to order, not stock value. Dashboards adapt automatically.
- **Reorder level** — leave blank and it'll be **calculated automatically** from your
  sales history (average monthly sellout over the lead time you set on the Dashboard).
- **Expiry date** — leave blank for non-perishables.

The app recognises common header variations automatically — e.g. `Item Code`,
`Model`, `Item Group`, `Cost Price`, `Stock Qty` all work, not just the exact
names below.
""")

sample = utils.sample_stock_template()
st.download_button(
    "⬇️ Download a sample template (Excel)",
    data=utils.to_excel_bytes({"stock_template": sample}),
    file_name="stock_upload_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

uploaded = st.file_uploader("Upload stock file (.xlsx or .csv)", type=["xlsx", "csv"])

if uploaded:
    try:
        if uploaded.name.lower().endswith(".csv"):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Could not read that file: {e}")
        st.stop()

    df, found = utils.normalize_columns(
        raw, ["sku", "product_name", "category", "quantity", "unit_cost", "reorder_level", "expiry_date"]
    )

    missing_required = [c for c in ["product_name", "quantity"] if c not in found]
    if missing_required:
        st.error(f"Couldn't find a column for: {', '.join(missing_required)}. "
                  f"Please make sure your file has a product name and a quantity column.")
    else:
        if "sku" not in found:
            df["sku"] = df["product_name"]
            st.info("No SKU/model/item-code column found — using product name as the identifier instead.")
        if "category" not in found:
            df["category"] = ""
        if "unit_cost" not in found:
            df["unit_cost"] = None
            st.info("No cost column found — reports will focus on quantities only.")
        if "reorder_level" not in found:
            df["reorder_level"] = None
            st.info("No reorder-level column found — this will be calculated automatically from your sales history.")
        if "expiry_date" not in found:
            df["expiry_date"] = ""

        st.success(f"File looks good — {len(df)} row(s) found.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        if st.button("✅ Confirm & Save as current stock", type="primary"):
            db.replace_stock(user["id"], df)
            st.success("Stock saved. Head to the Dashboard to see your updated numbers.")

st.divider()
current = db.get_stock_df(user["id"])
if not current.empty:
    st.subheader("Current saved stock")
    st.dataframe(current.drop(columns=["user_id"]), use_container_width=True, hide_index=True)
else:
    st.info("No stock saved yet — the Dashboard is showing example data until you upload your own.")
