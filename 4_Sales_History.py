import streamlit as st
import pandas as pd
import plotly.express as px
import db
import utils

st.set_page_config(page_title="Sales History • BRIM", page_icon="📈", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("📈 Sales History")

user = st.session_state.user
if not user:
    st.warning("Please log in first (see the Login page in the sidebar).")
    st.stop()

st.markdown("""
Upload your **past sales records** — the more history you provide, the more
accurate your average sellout (and replenishment suggestions) will be.
New uploads are **added** to your existing sales history (they don't overwrite it).

**Only a product name and quantity sold are required.** A sale date is
**optional** — if you leave it out, just tell us roughly how many months of
sales the file covers, and we'll average it out monthly. SKU/model is also
optional and will fall back to the product name if missing.
""")

sample = utils.sample_sales_template()
st.download_button(
    "⬇️ Download a sample template (Excel)",
    data=utils.to_excel_bytes({"sales_template": sample}),
    file_name="sales_history_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

uploaded = st.file_uploader("Upload sales history file (.xlsx or .csv)", type=["xlsx", "csv"])

if uploaded:
    try:
        if uploaded.name.lower().endswith(".csv"):
            raw = pd.read_csv(uploaded)
        else:
            raw = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Could not read that file: {e}")
        st.stop()

    df, found = utils.normalize_columns(raw, ["sku", "product_name", "quantity_sold", "sale_date"])

    missing_required = [c for c in ["product_name", "quantity_sold"] if c not in found]
    if missing_required:
        st.error(f"Couldn't find a column for: {', '.join(missing_required)}. "
                  f"Please make sure your file has a product name and a quantity-sold column.")
    else:
        if "sku" not in found:
            df["sku"] = df["product_name"]

        has_dates = False
        if "sale_date" in found:
            parsed = pd.to_datetime(df["sale_date"], errors="coerce")
            has_dates = parsed.notna().any()

        months_covered = db.get_sales_period_months(user["id"])
        if not has_dates:
            df["sale_date"] = ""
            st.info("No usable sale-date column found — tell us roughly how long this file covers instead, "
                      "and we'll calculate a monthly average from the totals.")
            months_covered = st.number_input(
                "Roughly how many months of sales does this file cover?",
                min_value=1, max_value=24, value=months_covered
            )

        st.success(f"File looks good — {len(df)} row(s) found.")
        st.dataframe(df, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)
        if c1.button("➕ Add to sales history", type="primary"):
            db.append_sales(user["id"], df)
            if not has_dates:
                db.set_sales_period_months(user["id"], months_covered)
            st.success("Sales history updated.")
        if c2.button("🗑️ Clear all my sales history instead"):
            db.clear_sales(user["id"])
            st.warning("Sales history cleared.")

st.divider()
sales_df = db.get_sales_df(user["id"])
if not sales_df.empty:
    st.subheader("Average sellout (calculated from your uploads)")
    months_covered = db.get_sales_period_months(user["id"])
    velocity = utils.average_daily_sellout(sales_df, months_covered=months_covered)
    st.dataframe(velocity, use_container_width=True, hide_index=True)

    top = velocity.sort_values("avg_monthly_sales", ascending=False).head(15)
    fig = px.bar(top, x="product_name", y="avg_monthly_sales",
                 title="Top movers — average units sold per month", color="avg_monthly_sales",
                 color_continuous_scale="Blues")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Raw sales history"):
        st.dataframe(sales_df.drop(columns=["user_id"]), use_container_width=True, hide_index=True)
else:
    st.info("No sales history uploaded yet. Replenishment suggestions and auto reorder levels will be "
            "limited until you add some.")
