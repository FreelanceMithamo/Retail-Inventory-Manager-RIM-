import streamlit as st
import db
import utils
import tiers
from datetime import date

st.set_page_config(page_title="Reports • BRIM", page_icon="📑", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("📑 Downloadable Reports")

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
    st.caption(f"Plan: **{sub['tier']}** — you can download: {', '.join(unlocked_reports)}")
else:
    unlocked_reports = ["Stockouts", "Replenishment", "Overstock", "Aged stock", "Short expiries"]

stock_df = db.get_stock_df(user["id"])
sales_df = db.get_sales_df(user["id"])
months_covered = db.get_sales_period_months(user["id"])

if stock_df.empty:
    st.info("No stock data yet. Go to Upload Stock first — reports will be available once you have.")
    st.stop()

master, has_cost = utils.build_master_view(stock_df, sales_df, months_covered=months_covered)
if not has_cost:
    st.caption("No cost data supplied — reports are focused on quantities rather than stock value.")

report_map = {
    "Replenishment": utils.replenishment_report(master),
    "Stockouts": utils.stockouts_report(master),
    "Overstock": utils.overstock_report(master, has_cost),
    "Aged stock": utils.aged_stock_report(master, has_cost),
    "Short expiries": utils.short_expiry_report(master, has_cost),
}

st.markdown("Download individual reports, or everything you're entitled to in one workbook.")

cols = st.columns(len(report_map))
for i, (name, rep_df) in enumerate(report_map.items()):
    with cols[i]:
        locked = name not in unlocked_reports
        st.markdown(f"**{name}**")
        if locked:
            st.caption("🔒 Upgrade your plan to unlock")
        else:
            st.caption(f"{0 if rep_df.empty else len(rep_df)} row(s)")
            st.download_button(
                f"⬇️ {name}.xlsx",
                data=utils.to_excel_bytes({name: rep_df}),
                file_name=f"{name.lower().replace(' ', '_')}_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_{name}",
            )

st.divider()
allowed_sheets = {k: v for k, v in report_map.items() if k in unlocked_reports}
if allowed_sheets:
    st.download_button(
        "⬇️ Download ALL unlocked reports in one workbook",
        data=utils.to_excel_bytes(allowed_sheets),
        file_name=f"brim_full_report_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
