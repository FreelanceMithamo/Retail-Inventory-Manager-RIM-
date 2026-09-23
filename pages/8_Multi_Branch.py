import streamlit as st
import pandas as pd
import plotly.express as px
import db
import utils
import tiers
from datetime import date

st.set_page_config(page_title="Multi-Branch • BRIM", page_icon="🏬", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🏬 Multi-Branch Module")
st.markdown("""
For businesses with **more than one shop, branch or outlet**. Upload stock and
sales per branch, then get replenishment, stockout, overstock and aged-stock
reports **for each branch individually**, or compare branches side by side.
""")

user = st.session_state.user
if not user:
    st.warning("Please log in first (see the Login page in the sidebar).")
    st.stop()

if user["role"] != "admin":
    sub = db.get_active_subscription(user["id"])
    if not sub or (db.subscription_days_left(sub) or -1) < 0:
        st.error("Your subscription is inactive or expired. Please visit the Pricing page to subscribe/renew.")
        st.stop()
    unlocked_reports = tiers.TIERS[sub["tier"]]["reports"]
else:
    unlocked_reports = ["Stockouts", "Replenishment", "Overstock", "Aged stock", "Short expiries"]

tab_stock, tab_sales, tab_dash = st.tabs(["📤 Upload Branch Stock", "📈 Upload Branch Sales", "📊 Branch Dashboards & Reports"])

# ============================================================
# TAB 1 — UPLOAD BRANCH STOCK (long format: one row per branch+item)
# ============================================================
with tab_stock:
    st.markdown("""
    One row per **branch + item**. Required columns: **Branch**, a product
    name (or item group), and **Quantity**. SKU/model, category, cost,
    reorder level and expiry date are all optional, same as the single-shop
    Upload Stock page.
    """)
    sample = utils.sample_branch_stock_template()
    st.download_button(
        "⬇️ Download a sample template (Excel)",
        data=utils.to_excel_bytes({"branch_stock_template": sample}),
        file_name="branch_stock_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="branch_stock_template_dl",
    )

    up1 = st.file_uploader("Upload branch stock file (.xlsx or .csv)", type=["xlsx", "csv"], key="branch_stock_upload")
    if up1:
        try:
            raw = pd.read_csv(up1) if up1.name.lower().endswith(".csv") else pd.read_excel(up1)
        except Exception as e:
            st.error(f"Could not read that file: {e}")
            raw = None

        if raw is not None:
            df, found = utils.normalize_columns(
                raw, ["branch", "sku", "product_name", "category", "quantity", "unit_cost", "reorder_level", "expiry_date"]
            )
            missing = [c for c in ["branch", "product_name", "quantity"] if c not in found]
            if missing:
                st.error(f"Couldn't find a column for: {', '.join(missing)}. "
                          f"A branch stock file needs a Branch, a product name, and a Quantity column.")
            else:
                if "sku" not in found:
                    df["sku"] = df["product_name"]
                for col in ["category", "unit_cost", "reorder_level", "expiry_date"]:
                    if col not in found:
                        df[col] = None if col in ("unit_cost", "reorder_level") else ""
                st.success(f"File looks good — {len(df)} row(s) across {df['branch'].nunique()} branch(es).")
                st.dataframe(df, use_container_width=True, hide_index=True)
                if st.button("✅ Confirm & Save as current branch stock", type="primary"):
                    db.replace_branch_stock(user["id"], df)
                    st.success("Branch stock saved. Head to the Dashboards tab to see it.")

    st.divider()
    current = db.get_branch_stock_df(user["id"])
    if not current.empty:
        st.subheader("Current saved branch stock")
        st.dataframe(current.drop(columns=["user_id"]), use_container_width=True, hide_index=True)
    else:
        st.info("No branch stock saved yet.")

# ============================================================
# TAB 2 — UPLOAD BRANCH SALES (wide format: branches as columns to the right)
# ============================================================
with tab_sales:
    st.markdown("""
    This is a **wide** sheet: a product name (and optionally SKU/model)
    on the left, then **one column per branch** with units sold, optionally
    with a **Total** column on the far right (the total column, if present,
    is ignored — it's recalculated from the branch columns automatically).
    """)
    sample2 = utils.sample_branch_sales_template()
    st.download_button(
        "⬇️ Download a sample template (Excel)",
        data=utils.to_excel_bytes({"branch_sales_template": sample2}),
        file_name="branch_sales_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="branch_sales_template_dl",
    )

    up2 = st.file_uploader("Upload branch sales file (.xlsx or .csv)", type=["xlsx", "csv"], key="branch_sales_upload")
    if up2:
        try:
            raw2 = pd.read_csv(up2) if up2.name.lower().endswith(".csv") else pd.read_excel(up2)
        except Exception as e:
            st.error(f"Could not read that file: {e}")
            raw2 = None

        if raw2 is not None:
            norm2, found2 = utils.normalize_columns(raw2, ["sku", "product_name"])
            if "product_name" not in found2:
                st.error("Couldn't find a product name / item group column in this file.")
            else:
                product_col = "product_name"
                sku_col = "sku" if "sku" in found2 else None
                other_cols = [c for c in norm2.columns if c not in (product_col, sku_col)]
                # Drop an obvious "Total" column from the default selection, but leave it selectable
                default_branches = [c for c in other_cols if utils._clean(c) not in ("total", "totalsold", "grandtotal")]

                st.write("Select which columns represent each **branch's** units sold:")
                branch_cols = st.multiselect("Branch columns", options=other_cols, default=default_branches)

                if branch_cols:
                    long_df = utils.melt_branch_sales(norm2, branch_cols, product_col=product_col, sku_col=sku_col)
                    st.success(f"Detected {len(branch_cols)} branch(es), {len(long_df)} sales row(s) after unpacking.")
                    st.dataframe(long_df, use_container_width=True, hide_index=True)

                    months_covered = db.get_sales_period_months(user["id"])
                    months_covered = st.number_input(
                        "Roughly how many months of sales does this file cover?",
                        min_value=1, max_value=24, value=months_covered
                    )

                    c1, c2 = st.columns(2)
                    if c1.button("➕ Add to branch sales history", type="primary"):
                        db.append_branch_sales(user["id"], long_df)
                        db.set_sales_period_months(user["id"], months_covered)
                        st.success("Branch sales history updated.")
                    if c2.button("🗑️ Clear all branch sales history instead"):
                        db.clear_branch_sales(user["id"])
                        st.warning("Branch sales history cleared.")
                else:
                    st.info("Pick at least one branch column to continue.")

    st.divider()
    current_sales = db.get_branch_sales_df(user["id"])
    if not current_sales.empty:
        with st.expander("Current saved branch sales history"):
            st.dataframe(current_sales.drop(columns=["user_id"]), use_container_width=True, hide_index=True)
    else:
        st.info("No branch sales history saved yet.")

# ============================================================
# TAB 3 — BRANCH DASHBOARDS & REPORTS
# ============================================================
with tab_dash:
    branch_stock_df = db.get_branch_stock_df(user["id"])
    branch_sales_df = db.get_branch_sales_df(user["id"])
    months_covered = db.get_sales_period_months(user["id"])

    if branch_stock_df.empty:
        st.info("Upload branch stock first (see the 'Upload Branch Stock' tab) to see dashboards here.")
        st.stop()

    branches = sorted(branch_stock_df["branch"].dropna().unique().tolist())
    view = st.selectbox("View", ["🔍 Compare all branches"] + branches)

    with st.expander("⚙️ Settings", expanded=False):
        c1, c2, c3 = st.columns(3)
        lead_time = c1.number_input("Supplier lead time (days)", min_value=0, value=7, key="mb_lead")
        cover_days = c2.number_input("Target stock cover (days)", min_value=1, value=14, key="mb_cover")
        expiry_alert_days = c3.number_input("Flag expiries within (days)", min_value=1, value=30, key="mb_exp")
        aged_days = st.number_input("Flag as aged if cover exceeds (days) or no sales recorded",
                                      min_value=1, value=60, key="mb_aged")

    def branch_master(branch_name):
        s = branch_stock_df[branch_stock_df["branch"] == branch_name]
        sa = branch_sales_df[branch_sales_df["branch"] == branch_name] if not branch_sales_df.empty else branch_sales_df
        return utils.build_master_view(s, sa, lead_time_days=lead_time, cover_days=cover_days,
                                        expiry_alert_days=expiry_alert_days, aged_days=aged_days,
                                        months_covered=months_covered)

    if view == "🔍 Compare all branches":
        st.subheader("Branch comparison")
        rows = []
        for b in branches:
            m, hc = branch_master(b)
            if m.empty:
                continue
            rows.append({
                "branch": b,
                "SKUs": len(m),
                "Stockouts": int(m["is_stockout"].sum()),
                "Low stock": int(m["is_low_stock"].sum()),
                "Overstock": int(m["is_overstock"].sum()),
                "Aged": int(m["is_aged"].sum()),
                "Short expiry": int(m["is_short_expiry"].sum()),
                "Units in stock": m["quantity"].sum(),
            })
        comp_df = pd.DataFrame(rows)
        if comp_df.empty:
            st.info("No branch data to compare yet.")
        else:
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
            melted = comp_df.melt(id_vars="branch",
                                   value_vars=["Stockouts", "Low stock", "Overstock", "Aged", "Short expiry"],
                                   var_name="issue", value_name="count")
            fig = px.bar(melted, x="branch", y="count", color="issue", barmode="group",
                         title="Issues by branch")
            st.plotly_chart(fig, use_container_width=True)

            all_sheets = {}
            for b in branches:
                m, hc = branch_master(b)
                if m.empty:
                    continue
                all_sheets[f"{b[:20]} Replenishment"] = utils.replenishment_report(m)
                all_sheets[f"{b[:20]} Stockouts"] = utils.stockouts_report(m)
            if all_sheets:
                st.download_button(
                    "⬇️ Download all-branches workbook (Excel)",
                    data=utils.to_excel_bytes(all_sheets),
                    file_name=f"branch_comparison_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
    else:
        master, has_cost = branch_master(view)
        if master.empty:
            st.info(f"No stock recorded for **{view}** yet.")
            st.stop()

        st.subheader(f"Dashboard — {view}")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("SKUs tracked", len(master))
        k2.metric("Stockouts", int(master["is_stockout"].sum()))
        k3.metric("Low stock", int(master["is_low_stock"].sum()))
        k4.metric("Overstock", int(master["is_overstock"].sum()))

        rep_tabs = st.tabs(["🔁 Replenishment", "⚠️ Stockouts", "📦 Overstock", "⏳ Aged Stock", "⌛ Short Expiries"])

        with rep_tabs[0]:
            rep = utils.replenishment_report(master)
            st.dataframe(rep, use_container_width=True, hide_index=True) if not rep.empty else st.success("Nothing needs reordering.")
        with rep_tabs[1]:
            so = utils.stockouts_report(master)
            st.dataframe(so, use_container_width=True, hide_index=True) if not so.empty else st.success("No stockouts.")
        with rep_tabs[2]:
            ov = utils.overstock_report(master, has_cost)
            st.dataframe(ov, use_container_width=True, hide_index=True) if not ov.empty else st.success("No overstock.")
        with rep_tabs[3]:
            ag = utils.aged_stock_report(master, has_cost)
            st.dataframe(ag, use_container_width=True, hide_index=True) if not ag.empty else st.success("No aged stock.")
        with rep_tabs[4]:
            se = utils.short_expiry_report(master, has_cost)
            st.dataframe(se, use_container_width=True, hide_index=True) if not se.empty else st.success("Nothing expiring soon.")

        st.download_button(
            f"⬇️ Download {view} workbook (Excel)",
            data=utils.to_excel_bytes({
                "Replenishment": utils.replenishment_report(master),
                "Stockouts": utils.stockouts_report(master),
                "Overstock": utils.overstock_report(master, has_cost),
                "Aged stock": utils.aged_stock_report(master, has_cost),
                "Short expiries": utils.short_expiry_report(master, has_cost),
            }),
            file_name=f"{view.replace(' ', '_')}_report_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
