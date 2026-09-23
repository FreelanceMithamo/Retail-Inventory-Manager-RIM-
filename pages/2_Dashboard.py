import streamlit as st
import plotly.express as px
import db
import utils
import tiers

st.set_page_config(page_title="Dashboard • BRIM", page_icon="📊", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("📊 Dashboards")

user = st.session_state.user
if not user:
    st.warning("Please log in first (see the Login page in the sidebar).")
    st.stop()

if user["role"] != "admin":
    sub = db.get_active_subscription(user["id"])
    if not sub or (db.subscription_days_left(sub) or -1) < 0:
        st.error("Your subscription is inactive or expired. Please visit the Pricing page to subscribe/renew.")
        st.stop()
    tier = sub["tier"]
    unlocked_reports = tiers.TIERS[tier]["reports"]
    st.caption(f"Plan: **{tier}** — unlocked reports: {', '.join(unlocked_reports)}")
else:
    unlocked_reports = ["Stockouts", "Replenishment", "Overstock", "Aged stock", "Short expiries"]
    st.caption("Admin view — all reports unlocked.")

stock_df = db.get_stock_df(user["id"])
sales_df = db.get_sales_df(user["id"])
months_covered = db.get_sales_period_months(user["id"])

is_demo = stock_df.empty
if is_demo:
    st.info("👋 **You haven't uploaded stock yet — this is example data** (a chemist carrying several "
            "drugs), so you can see what your dashboards will look like. Upload your own stock and it "
            "replaces this automatically.")
    stock_df, sales_df = utils.sample_demo_data()
    months_covered = 3

with st.expander("⚙️ Dashboard settings", expanded=False):
    c1, c2, c3 = st.columns(3)
    lead_time = c1.number_input("Supplier lead time (days)", min_value=0, value=7)
    cover_days = c2.number_input("Target stock cover (days)", min_value=1, value=14)
    expiry_alert_days = c3.number_input("Flag expiries within (days)", min_value=1, value=30)
    c4, c5 = st.columns(2)
    aged_days = c4.number_input("Flag as aged if cover exceeds (days) or no sales recorded", min_value=1, value=60)
    safety_buffer_pct = c5.number_input("Safety buffer on auto reorder levels (%)", min_value=0, value=20)

master, has_cost = utils.build_master_view(
    stock_df, sales_df,
    lead_time_days=lead_time, cover_days=cover_days,
    expiry_alert_days=expiry_alert_days, aged_days=aged_days,
    safety_buffer_pct=safety_buffer_pct, months_covered=months_covered,
)

# ---------- KPI ROW ----------
if has_cost:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("SKUs tracked", len(master))
    k2.metric("Stock value", f"KES {master['stock_value'].sum():,.0f}")
    k3.metric("Stockouts", int(master["is_stockout"].sum()))
    k4.metric("Low stock", int(master["is_low_stock"].sum()))
    k5.metric("Short expiry", int(master["is_short_expiry"].sum()) if "Short expiries" in unlocked_reports else 0)
else:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("SKUs tracked", len(master))
    k2.metric("Total units in stock", f"{master['quantity'].sum():,.0f}")
    k3.metric("Stockouts", int(master["is_stockout"].sum()))
    k4.metric("Low stock", int(master["is_low_stock"].sum()))
    k5.metric("Short expiry", int(master["is_short_expiry"].sum()) if "Short expiries" in unlocked_reports else 0)
    st.caption("No cost data supplied — dashboards are focused on quantities rather than stock value.")

st.divider()

tab_labels = ["🔁 Replenishment", "⚠️ Stockouts"]
if "Overstock" in unlocked_reports:
    tab_labels.append("📦 Overstock")
if "Aged stock" in unlocked_reports:
    tab_labels.append("⏳ Aged Stock")
if "Short expiries" in unlocked_reports:
    tab_labels.append("⌛ Short Expiries")

tabs = st.tabs(tab_labels)
idx = 0

# --- Replenishment ---
with tabs[idx]:
    rep = utils.replenishment_report(master)
    st.markdown("Items at or below reorder level, with a suggested order quantity based on your "
                "average sellout, supplier lead time, and target cover. Reorder levels marked "
                "**auto** were calculated from your sales history, not uploaded manually.")
    if rep.empty:
        st.success("Nothing needs reordering right now. 🎉")
    else:
        display_rep = rep.copy()
        display_rep["reorder_level"] = display_rep.apply(
            lambda r: f"{r['reorder_level']:.0f} (auto)" if r["reorder_level_is_auto"] else f"{r['reorder_level']:.0f}",
            axis=1
        )
        st.dataframe(display_rep.drop(columns=["reorder_level_is_auto"]), use_container_width=True, hide_index=True)
        fig = px.bar(rep.head(15), x="product_name", y="suggested_order_qty",
                     title="Top suggested order quantities", color="suggested_order_qty",
                     color_continuous_scale="Greens")
        st.plotly_chart(fig, use_container_width=True)
idx += 1

# --- Stockouts ---
with tabs[idx]:
    so = utils.stockouts_report(master)
    st.markdown("Products currently at **zero** quantity on hand.")
    if so.empty:
        st.success("No stockouts right now. 🎉")
    else:
        st.dataframe(so, use_container_width=True, hide_index=True)
        fig = px.bar(so, x="product_name", y="avg_daily_sales", title="Avg daily sales of out-of-stock items",
                     color_discrete_sequence=["#E53935"])
        st.plotly_chart(fig, use_container_width=True)
idx += 1

# --- Overstock ---
if "Overstock" in unlocked_reports:
    with tabs[idx]:
        ov = utils.overstock_report(master, has_cost)
        st.markdown("Products with far more cover than your target.")
        if ov.empty:
            st.success("No significant overstock detected.")
        else:
            st.dataframe(ov, use_container_width=True, hide_index=True)
            value_field = "stock_value" if has_cost else "quantity"
            fig = px.treemap(ov, path=["product_name"], values=value_field,
                              title=f"Overstocked {'value' if has_cost else 'quantity'} by product",
                              color=value_field, color_continuous_scale="Oranges")
            st.plotly_chart(fig, use_container_width=True)
    idx += 1

# --- Aged Stock ---
if "Aged stock" in unlocked_reports:
    with tabs[idx]:
        aged = utils.aged_stock_report(master, has_cost)
        st.markdown("Products with little or no recorded sales, or far exceeding your aged-stock threshold.")
        if aged.empty:
            st.success("No aged stock flagged.")
        else:
            st.dataframe(aged, use_container_width=True, hide_index=True)
            y_field = "stock_value" if has_cost else "quantity"
            fig = px.bar(aged.head(15), x="product_name", y=y_field,
                         title=f"Aged stock {'value' if has_cost else 'quantity'} tied up",
                         color_discrete_sequence=["#8D6E63"])
            st.plotly_chart(fig, use_container_width=True)
    idx += 1

# --- Short Expiries ---
if "Short expiries" in unlocked_reports:
    with tabs[idx]:
        exp = utils.short_expiry_report(master, has_cost)
        st.markdown("Products expiring soon — prioritize discounting or promotions to avoid write-offs.")
        if exp.empty:
            st.success("Nothing expiring soon.")
        else:
            st.dataframe(exp, use_container_width=True, hide_index=True)
            fig = px.bar(exp, x="product_name", y="days_to_expiry", title="Days to expiry (shortest first)",
                         color="days_to_expiry", color_continuous_scale="Reds_r")
            st.plotly_chart(fig, use_container_width=True)
