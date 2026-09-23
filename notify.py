"""
notify.py — alerts YOU (the admin) the moment a customer clicks
"Confirm Subscription", so you can follow up by email/phone and collect
payment offline. No M-Pesa or payment gateway involved — this is a
heads-up message only.

Two options are supported, both optional and both configured through
Streamlit "Secrets" (never hard-code these in the code or commit them to
GitHub). If neither is set up, alerts are still recorded inside the app
(Admin page → Notifications) — WhatsApp/SMS is just an instant bonus on
top of that.

────────────────────────────────────────────────────────────────────────
OPTION A — WhatsApp via CallMeBot (free, easiest, takes ~2 minutes)
────────────────────────────────────────────────────────────────────────
1. On the WhatsApp number you want alerts sent to, add this contact:
       +34 644 59 71 66
2. Send that contact exactly this message (from your WhatsApp):
       I allow callmebot to send me messages
3. Within a minute you'll get a reply containing your personal API key
   (a short number).
4. In your app's Secrets, add:
       CALLMEBOT_PHONE = "2547XXXXXXXX"   (your number, digits only, no +)
       CALLMEBOT_APIKEY = "123456"        (the key CallMeBot sent you)

────────────────────────────────────────────────────────────────────────
OPTION B — Real SMS via Africa's Talking (small cost per SMS)
────────────────────────────────────────────────────────────────────────
1. Create a free account at https://africastalking.com
2. In the dashboard, note your Username and API Key.
3. In your app's Secrets, add:
       AT_USERNAME = "your_username"
       AT_API_KEY = "your_api_key"
       AT_RECIPIENT = "+2547XXXXXXXX"     (your number, international format)

If both are configured, WhatsApp is tried first, then SMS as a fallback.
"""

import requests
import streamlit as st
import db


def _get_secret(key):
    """Safely reads a Streamlit secret. Returns None if no secrets.toml
    exists at all (a fresh deploy with nothing configured yet) instead of
    raising — notifications are optional, so a missing config should never
    break the subscribe flow."""
    try:
        return st.secrets.get(key)
    except Exception:
        return None


def _send_whatsapp_callmebot(message):
    phone = _get_secret("CALLMEBOT_PHONE")
    apikey = _get_secret("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        return False, "CallMeBot not configured"
    try:
        r = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": phone, "text": message, "apikey": apikey},
            timeout=10,
        )
        if r.status_code == 200:
            return True, "Sent via WhatsApp (CallMeBot)"
        return False, f"CallMeBot error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"CallMeBot exception: {e}"


def _send_sms_africastalking(message):
    username = _get_secret("AT_USERNAME")
    api_key = _get_secret("AT_API_KEY")
    recipient = _get_secret("AT_RECIPIENT")
    if not (username and api_key and recipient):
        return False, "Africa's Talking not configured"
    try:
        url = "https://api.africastalking.com/version1/messaging"
        if username == "sandbox":
            url = "https://api.sandbox.africastalking.com/version1/messaging"
        r = requests.post(
            url,
            headers={
                "apiKey": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={"username": username, "to": recipient, "message": message},
            timeout=10,
        )
        if r.status_code in (200, 201):
            return True, "Sent via SMS (Africa's Talking)"
        return False, f"Africa's Talking error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"Africa's Talking exception: {e}"


def notify_admin(message):
    """Tries WhatsApp, then SMS, then always logs the event in-app. Never raises."""
    sent, detail = _send_whatsapp_callmebot(message)
    if not sent:
        sent, detail = _send_sms_africastalking(message)
    db.log_notification(message, sent, detail)
    return sent, detail
