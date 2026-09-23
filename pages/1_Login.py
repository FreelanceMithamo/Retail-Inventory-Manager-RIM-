import streamlit as st
import db
import auth

st.set_page_config(page_title="Login • BRIM", page_icon="🔐", layout="wide")
db.init_db()

if "user" not in st.session_state:
    st.session_state.user = None

st.title("🔐 Login / Sign Up")

if st.session_state.user:
    st.success(f"You're already signed in as **{st.session_state.user['username']}**.")
    st.caption("Use 'Sign out' in the sidebar to switch accounts.")
    st.stop()

tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

# ---------------- LOGIN ----------------
with tab_login:
    with st.form("login_form"):
        identifier = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", use_container_width=True)

    if submitted:
        if not identifier or not password:
            st.error("Please fill in both fields.")
        else:
            ok, result = auth.login(identifier, password)
            if ok:
                st.session_state.user = result
                st.success(f"Welcome back, {result['username']}!")
                st.rerun()
            else:
                st.error(result)

    with st.expander("Change my password"):
        st.caption("You must know your current password to change it. If you're locked out, contact support.")
        with st.form("change_pw_form"):
            u = st.text_input("Username or Email", key="cp_user")
            old = st.text_input("Current password", type="password", key="cp_old")
            new = st.text_input("New password", type="password", key="cp_new")
            cp_submit = st.form_submit_button("Update Password")
        if cp_submit:
            user = db.get_user_by_username(u) or db.get_user_by_email(u)
            if not user:
                st.error("No account found with that username/email.")
            else:
                ok, msg = auth.change_password(user["id"], old, new)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# ---------------- SIGNUP ----------------
with tab_signup:
    st.caption("Create your business account. You'll choose a subscription plan on the Pricing page after signing up.")
    with st.form("signup_form"):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Choose a username")
            email = st.text_input("Email address")
            phone = st.text_input("Phone number (optional)")
        with c2:
            business_name = st.text_input("Business name")
            business_type = st.selectbox(
                "Business type",
                ["Chemist / Pharmacy", "Butchery", "Small Retail Shop / Mini-Mart",
                 "Hardware Store", "Electronics Shop", "Other"]
            )
            password = st.text_input("Choose a password", type="password")
        signup_submit = st.form_submit_button("Create Account", use_container_width=True)

    if signup_submit:
        if not all([username, email, business_name, password]):
            st.error("Username, email, business name and password are required.")
        else:
            ok, result = auth.signup(username, email, password, business_name, business_type, phone)
            if ok:
                st.success("Account created! Please log in on the 'Log In' tab.")
                st.info("Next step: visit the **Pricing** page to activate a subscription plan.")
            else:
                st.error(result)
