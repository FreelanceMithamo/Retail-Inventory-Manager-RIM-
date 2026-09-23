import streamlit as st
import db
import tiers
import notify

st.set_page_config(page_title="Pricing • BRIM", page_icon="💳", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("💳 Rate Card & Subscriptions")
st.markdown("One flat monthly subscription per tier covers **all reports and support** included in that "
            "tier — no per-report add-on fees.")

cols = st.columns(3)
for i, tier_name in enumerate(tiers.TIER_ORDER):
    t = tiers.TIERS[tier_name]
    with cols[i]:
        st.markdown(
            f"<div style='border:2px solid {t['color']};border-radius:12px;padding:16px;'>"
            f"<h3 style='color:{t['color']};margin-top:0;'>{tier_name}</h3>"
            f"<p style='color:gray;margin-top:-10px;'>{t['tagline']}</p>"
            f"<h2>KES {t['price_kes']:,} <span style='font-size:14px;color:gray;'>/ month</span></h2>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Includes:**")
        for f in t["features"]:
            st.markdown(f"- {f}")

st.caption("Prices shown in KES. Adjust currency/pricing in `tiers.py` to suit your market.")

st.divider()

user = st.session_state.user
if not user:
    st.info("Log in or sign up to subscribe to a plan.")
    st.stop()

if user["role"] == "admin":
    st.info("You're signed in as admin — manage customer subscriptions from the Admin page.")
    st.stop()

st.subheader("Subscribe / Renew")
current_sub = db.get_active_subscription(user["id"])
if current_sub:
    days_left = db.subscription_days_left(current_sub)
    if days_left is not None and days_left >= 0:
        st.success(f"Current plan: **{current_sub['tier']}** — {days_left} day(s) remaining.")
    else:
        st.error(f"Your **{current_sub['tier']}** plan expired {abs(days_left)} day(s) ago. Please renew below.")
else:
    st.warning("You don't have an active subscription yet.")

with st.form("subscribe_form"):
    chosen_tier = st.selectbox("Choose a plan", tiers.TIER_ORDER,
                                index=tiers.TIER_ORDER.index(current_sub["tier"]) if current_sub else 0)
    months = st.selectbox("Billing period", [1, 3, 6, 12], format_func=lambda m: f"{m} month(s)")
    total = tiers.TIERS[chosen_tier]["price_kes"] * months
    st.markdown(f"**Total due: KES {total:,}**")
    st.caption("This demo records the subscription immediately. Wire this button up to your real payment "
               "gateway (e.g. M-Pesa Daraja, Stripe, Flutterwave) before going live.")
    confirm = st.form_submit_button("Confirm Subscription", type="primary")

if confirm:
    db.create_subscription(user["id"], chosen_tier, months)

    message = (
        f"BRIM: {user['business_name'] or user['username']} ({user['username']}) "
        f"picked {chosen_tier} — KES {total:,} for {months} month(s). "
        f"Email: {user['email']}"
        + (f", Phone: {user['phone']}" if user.get("phone") else "")
        + ". Follow up to collect payment."
    )
    sent, detail = notify.notify_admin(message)

    st.success(f"Subscribed to **{chosen_tier}** for {months} month(s). Refresh the Dashboard to see it unlocked.")
    if sent:
        st.caption("✅ The site owner has been notified.")
    else:
        st.caption("ℹ️ This request has been logged for the site owner to follow up on.")
    st.rerun()
