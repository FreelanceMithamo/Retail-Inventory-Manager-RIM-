import streamlit as st
from datetime import date
import db
import tiers

st.set_page_config(
    page_title="Basic Retail Inventory Manager",
    page_icon="📦",
    layout="wide",
)

db.init_db()

# ---------- SESSION STATE ----------
if "user" not in st.session_state:
    st.session_state.user = None  # dict once logged in
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False


def logged_in_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown("### 📦 BRIM")
        if user:
            st.success(f"Signed in as **{user['username']}**")
            if user["role"] == "admin":
                st.caption("Role: Admin")
            else:
                sub = db.get_active_subscription(user["id"])
                if sub:
                    days_left = db.subscription_days_left(sub)
                    if days_left is not None and days_left < 0:
                        st.error(f"{sub['tier']} plan — **expired**. Renew on the Pricing page.")
                    elif days_left is not None and days_left <= 5:
                        st.warning(f"{sub['tier']} plan — expires in {days_left} day(s).")
                    else:
                        st.info(f"{sub['tier']} plan — {days_left} day(s) left")
                else:
                    st.warning("No active subscription yet. Visit Pricing to subscribe.")
            if st.button("🚪 Sign out", use_container_width=True):
                st.session_state.user = None
                st.rerun()
        else:
            st.info("Not signed in. Use the **Login** page from the menu on the left.")


logged_in_sidebar()

# ---------- HERO ----------
st.title("📦 Basic Retail Inventory Manager")
st.subheader("Stock control and smart replenishment for small & medium retailers")

st.markdown("""
Built for **chemists, butcheries, small retail shops, mini-markets and other
small-to-medium businesses** who need to know — every day — what to reorder,
what's about to run out, what's sitting unsold, and what's about to expire.
""")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown("### 🔁\n**Replenishment**")
    st.caption("Know exactly what to order, based on your real average sellout — not guesswork.")
with col2:
    st.markdown("### ⚠️\n**Stockouts**")
    st.caption("Catch empty shelves and near-empty stock before customers do.")
with col3:
    st.markdown("### 📦\n**Overstock**")
    st.caption("Spot slow-moving stock tying up your cash.")
with col4:
    st.markdown("### ⏳\n**Aged & short-expiry stock**")
    st.caption("Flag stock sitting too long, and items nearing expiry — critical for chemists & food retailers.")
with col5:
    st.markdown("### 🏬\n**Multi-branch**")
    st.caption("Running more than one shop? Get every report per branch, or compare branches side by side.")

st.divider()

st.markdown("## What this does for your business")
left, right = st.columns(2)
with left:
    st.markdown("""
- **Upload your current stock** (Excel/CSV) any time — get an instant health check.
- **Upload your sales history** — the app calculates your **average sellout per product**,
  and can even work without exact sale dates, or a cost/reorder-level column.
- **See dashboards at a glance**: Replenishment, Stockouts, Overstock, Aged stock, and Short-expiry
  (for businesses that carry expiring goods) — populated with example data until you upload your own.
- **Running more than one branch?** The Multi-Branch module gives you every report per branch,
  or a side-by-side comparison across all of them.
- **Download any report as Excel** — share with a supplier, accountant, or business partner.
- **No spreadsheets to maintain by hand** — just upload, and the numbers do the thinking.
    """)
with right:
    st.markdown("""
### Why it matters
- Fewer **stockouts** → fewer lost sales.
- Less **overstock** → less cash tied up on the shelf.
- Fewer **write-offs** from expired or aged stock.
- **Faster, better-informed ordering decisions** — in minutes, not hours.
- Built for owners and managers with **no inventory-software experience**.
    """)

st.divider()

st.markdown("## Get started")
g1, g2, g3 = st.columns(3)
with g1:
    st.markdown("**1. Create an account**")
    st.caption("Go to the Login page in the sidebar and sign up with your business details.")
with g2:
    st.markdown("**2. Choose a plan**")
    st.caption("Bronze, Silver or Platinum — see the Pricing page for what's included.")
with g3:
    st.markdown("**3. Upload your stock & sales**")
    st.caption("Your dashboards populate automatically once you upload data.")

st.info("Use the menu on the left to navigate: **Login**, **Dashboard**, **Upload Stock**, "
        "**Sales History**, **Reports**, **Pricing**, **Multi-Branch** (for businesses with more than "
        "one shop), and (for the site owner) **Admin**.")

st.caption(f"© {date.today().year} Basic Retail Inventory Manager. Built for small business owners.")
