import streamlit as st
import pandas as pd
import db
import auth
import tiers

st.set_page_config(page_title="Admin • BRIM", page_icon="🛠️", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🛠️ Admin Panel")

user = st.session_state.user
if not user:
    st.warning("Please log in with an admin account (see the Login page).")
    st.stop()

if user["role"] != "admin":
    st.error("This page is restricted to admin accounts.")
    st.stop()

st.success(f"Signed in as admin: **{user['username']}**")

subs = db.all_subscriptions_with_users()
customers = db.list_customers()

# ---------- SUBSCRIBE-CLICK NOTIFICATIONS ----------
st.subheader("📨 Notifications")
st.caption("Every time a customer clicks 'Confirm Subscription' on the Pricing page, it's logged here — "
           "and, if WhatsApp/SMS is configured (see notify.py), sent straight to your phone too.")
notes = db.list_notifications(limit=30)
if notes:
    notes_df = pd.DataFrame(notes)[["created_at", "message", "sent", "detail"]]
    notes_df["sent"] = notes_df["sent"].map({1: "✅ delivered", 0: "⚠️ not delivered"})
    st.dataframe(notes_df, use_container_width=True, hide_index=True)
else:
    st.info("No subscription notifications yet.")

# ---------- EXPIRY ALERTS ----------
st.subheader("🔔 Subscription alerts")
expired, expiring_soon = [], []
for s in subs:
    days_left = db.subscription_days_left(s)
    if days_left is not None and days_left < 0:
        expired.append((s, days_left))
    elif days_left is not None and days_left <= 5:
        expiring_soon.append((s, days_left))

if not expired and not expiring_soon:
    st.success("No subscriptions expired or expiring within 5 days.")
else:
    for s, d in expired:
        st.error(f"**{s['business_name'] or s['username']}** ({s['email']}) — "
                  f"{s['tier']} plan expired {abs(d)} day(s) ago.")
    for s, d in expiring_soon:
        st.warning(f"**{s['business_name'] or s['username']}** ({s['email']}) — "
                    f"{s['tier']} plan expires in {d} day(s).")

st.divider()

# ---------- CUSTOMER OVERVIEW ----------
st.subheader("👥 Customers & subscriptions")
if subs:
    df = pd.DataFrame(subs)[["username", "email", "business_name", "tier", "start_date", "end_date", "status"]]
    df["days_left"] = [db.subscription_days_left(s) for s in subs]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No subscriptions recorded yet.")

with st.expander("All registered customer accounts"):
    if customers:
        st.dataframe(pd.DataFrame(customers)[["id", "username", "email", "business_name", "business_type", "created_at"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No customers signed up yet.")

st.divider()

# ---------- MANUAL RENEW / CHANGE PLAN ----------
st.subheader("🔁 Renew or change a customer's plan")
if customers:
    with st.form("admin_renew_form"):
        options = {f"{c['username']} ({c['email']})": c["id"] for c in customers}
        chosen = st.selectbox("Customer", list(options.keys()))
        tier = st.selectbox("Plan", tiers.TIER_ORDER)
        months = st.selectbox("Months", [1, 3, 6, 12])
        renew_submit = st.form_submit_button("Apply Subscription")
    if renew_submit:
        db.renew_subscription(options[chosen], tier, months)
        st.success(f"Applied {tier} ({months} month(s)) to {chosen}.")
        st.rerun()

st.divider()

# ---------- RESET A CUSTOMER PASSWORD ----------
st.subheader("🔑 Reset a customer's password")
if customers:
    with st.form("admin_reset_pw_form"):
        options2 = {f"{c['username']} ({c['email']})": c["id"] for c in customers}
        chosen2 = st.selectbox("Customer ", list(options2.keys()), key="reset_pw_select")
        new_pw = st.text_input("New temporary password", type="password")
        reset_submit = st.form_submit_button("Reset Password")
    if reset_submit:
        if len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            db.update_password(options2[chosen2], auth.hash_password(new_pw))
            st.success(f"Password reset for {chosen2}. Share the new password with them securely.")

st.divider()

# ---------- ADMIN'S OWN PASSWORD ----------
st.subheader("🔐 Change my own admin password")
with st.form("admin_own_pw_form"):
    old = st.text_input("Current password", type="password", key="admin_old")
    new = st.text_input("New password", type="password", key="admin_new")
    own_submit = st.form_submit_button("Update My Password")
if own_submit:
    ok, msg = auth.change_password(user["id"], old, new)
    if ok:
        st.success(msg)
    else:
        st.error(msg)
