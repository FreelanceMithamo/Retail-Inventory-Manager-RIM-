"""
tiers.py — single source of truth for the rate card / subscription tiers.
Edit prices and feature lists here; the Pricing page, signup flow, and
admin panel all read from this file.
"""

TIERS = {
    "Bronze": {
        "price_kes": 4500,
        "tagline": "Get the basics right",
        "reports": ["Stockouts", "Replenishment suggestions"],
        "features": [
            "Real-time stock upload",
            "Stockout & low-stock dashboard",
            "Replenishment suggestions (based on average sellout)",
            "1 user account",
            "Email support (48h response)",
        ],
        "color": "#CD7F32",
    },
    "Silver": {
        "price_kes": 7500,
        "tagline": "Full visibility, fewer losses",
        "reports": ["Stockouts", "Replenishment", "Overstock", "Aged stock"],
        "features": [
            "Everything in Bronze",
            "Overstock dashboard",
            "Aged stock dashboard",
            "Downloadable Excel reports",
            "Sales history trends",
            "Priority email support (24h response)",
        ],
        "color": "#9CA3AF",
    },
    "Platinum": {
        "price_kes": 10500,
        "tagline": "Built for expiry-sensitive stock",
        "reports": ["Stockouts", "Replenishment", "Overstock", "Aged stock", "Short expiries"],
        "features": [
            "Everything in Silver",
            "Short-expiry alerts (chemists, food, cosmetics, etc.)",
            "Unlimited stock & sales uploads",
            "All Excel reports, unlimited downloads",
            "Phone/WhatsApp support (same-day)",
            "Free onboarding call",
        ],
        "color": "#0F9D58",
    },
}

TIER_ORDER = ["Bronze", "Silver", "Platinum"]
