# 📦 Basic Retail Inventory Manager (BRIM)

Stock control and smart replenishment for small & medium retailers —
chemists, butcheries, small retail shops, mini-markets, and similar
businesses. Built with Streamlit + SQLite.

## Features

- **Sign up / Login** for retailer accounts, plus a separate **Admin** role.
- **Dashboards**: Replenishment suggestions, Stockouts, Overstock, Aged
  stock, and Short-expiry alerts — populated with example data (a chemist
  carrying several drugs) until you upload your own, so it's never blank.
- **Upload real-time stock** (Excel/CSV) — replaces your current snapshot.
  Only a product name and quantity are required; SKU, category, cost, and
  reorder level are all optional and the app recognises common header
  variations automatically (e.g. `Item Code`, `Item Group`, `Cost Price`).
- **Upload sales history** (Excel/CSV) — used to calculate average sellout
  per product, which drives replenishment suggestions and **automatically
  calculated reorder levels** (no need to work those out and upload them
  yourself). A sale-date column is optional too — without one, you just
  tell the app roughly how many months the file covers.
- **Cost is entirely optional.** Leave it out and every dashboard/report
  switches to quantity-based figures instead of stock value.
- **Multi-Branch module** for businesses with more than one shop: upload
  stock per branch and sales in a wide "branches across the top" sheet,
  then get replenishment/stockout/overstock/aged-stock reports for each
  branch individually, or compare all branches side by side.
- **Downloadable Excel reports** for every dashboard, gated by subscription
  tier.
- **Rate card**: Bronze / Silver / Platinum monthly subscriptions (edit
  prices and features in `tiers.py`).
- **Admin panel**: view all customers and subscriptions, get alerts when a
  subscription has expired or is expiring soon, manually renew/change a
  customer's plan, reset customer passwords, change your own password, sign
  out.
- **Subscribe-click notifications**: the moment a customer clicks "Confirm
  Subscription," you get a WhatsApp/SMS alert (optional setup) with their
  details and the plan they chose, so you can follow up and collect
  payment offline — see `notify.py`.

## Project structure

```
brim/
├── app.py                       # Landing page + session/sidebar
├── db.py                        # SQLite schema + data access
├── auth.py                      # Password hashing, login/signup
├── utils.py                     # Analytics, flexible column matching, demo data, Excel export
├── tiers.py                     # Rate card / subscription tier definitions
├── notify.py                    # WhatsApp/SMS alert to admin on new subscriptions
├── requirements.txt
├── .streamlit/config.toml       # Theme colors
├── .streamlit/secrets_example.toml  # Format for notification secrets
└── pages/
    ├── 1_Login.py
    ├── 2_Dashboard.py
    ├── 3_Upload_Stock.py
    ├── 4_Sales_History.py
    ├── 5_Reports.py
    ├── 6_Pricing.py
    ├── 7_Admin.py
    └── 8_Multi_Branch.py
```

## Run locally

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app creates `inventory.db` (SQLite) automatically on first run, and
seeds one default admin account:

- **username:** `admin`
- **password:** `Admin@123`

**Change this password immediately** (Login page → "Change my password", or
the Admin page → "Change my own admin password").

## Deploying this with zero IT knowledge

You don't need a server, hosting company, or any coding tools. Use
**Streamlit Community Cloud** — it's free, and it's built specifically to
run apps exactly like this one from a GitHub repository.

**Step 1 — Create a free GitHub account**
Go to [github.com](https://github.com) → Sign up. GitHub is just where the
app's files will live online.

**Step 2 — Create a new repository and upload the files**
1. Click the **+** icon (top right) → **New repository**.
2. Give it a name, e.g. `basic-retail-inventory-manager`. Leave everything
   else as default → **Create repository**.
3. On the new (empty) repository page, click **"uploading an existing
   file"**.
4. Unzip the folder you downloaded from this chat, then **drag the whole
   contents of the `brim` folder** (not the zip file itself, and not the
   `brim` folder wrapper — drag what's *inside* it: `app.py`, `db.py`,
   `pages`, etc.) straight onto that GitHub page.
5. Scroll down, click **Commit changes**. Your files are now online.

**Step 3 — Deploy on Streamlit**
1. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with
   the same GitHub account.
2. Click **"New app"**.
3. Pick your repository and branch (`main`), and set **"Main file
   path"** to `app.py`.
4. Click **Deploy**. Wait 2–3 minutes.
5. You'll get a live link like `yourapp.streamlit.app` — that's your
   website. Share it with anyone.

Streamlit installs everything listed in `requirements.txt` automatically —
you don't need to install anything yourself.

**Step 4 — Turn on phone notifications (optional but recommended)**
1. On your app's Streamlit Cloud page, click the **⋮** menu → **Settings**
   → **Secrets**.
2. Open `.streamlit/secrets_example.toml` in the files you uploaded, copy
   the WhatsApp (CallMeBot) lines into that Secrets box, fill in your
   details (see "Getting notified of new subscriptions" below), and save.
3. Your app restarts automatically with notifications turned on.

**Step 5 — Change the default admin password**
Log in with `admin` / `Admin@123` and change the password immediately
(Admin page → "Change my own admin password").

That's it — no server to maintain, no monthly hosting bill, and updates
are as simple as re-uploading a changed file to GitHub.

## Troubleshooting deployment

**"Failed to build pillow / numpy / pandas" (or the deploy just hangs on
"Installing requirements")** — Streamlit Cloud periodically upgrades the
Python version it runs on, and very old, tightly-pinned package versions
in `requirements.txt` sometimes don't have a ready-made install for the
newest Python yet, so it tries (and fails) to build one from scratch. This
repo's `requirements.txt` uses `>=` (minimum version) rather than `==`
(exact version) for this reason — it should always pick a version that
already works. If you ever see this error again after editing
`requirements.txt` yourself, the fix is the same: change any `==` back to
`>=`, commit, and the app will redeploy automatically.

**"Stuck at 'Spinning up manager process…'"** — this is a Streamlit-side
hiccup, not your files. Use the **⋮** menu on your app → **Reboot app**. If
it's still stuck after that, delete and redeploy the app fresh.

**Anything else** — click **"Manage app"** on your app's page to see the
live logs; they'll show exactly which step it's stuck or failing on.

### ⚠️ Important: SQLite is not persistent on Streamlit Cloud

Streamlit Community Cloud's filesystem resets on redeploys/reboots, which
will wipe the `inventory.db` SQLite file. This is fine for a demo, but for
a paid product with real customer data, swap the database layer for a
hosted database:

- Easiest options: [Supabase](https://supabase.com) or
  [Neon](https://neon.tech) (both have free-tier Postgres).
- You'd only need to edit `db.py` — everything else in the app calls the
  helper functions defined there, so the rest of the codebase doesn't
  change.
- Store the connection string in Streamlit's `st.secrets` (Settings →
  Secrets on Streamlit Cloud), never commit it to GitHub.

## Customizing the rate card

Edit `tiers.py` — prices (currently KES), feature lists, and which reports
each tier unlocks. The Pricing page, Dashboard, Reports, and Admin panel all
read from this one file.

## How subscriptions & payment work

There's **no payment gateway built in on purpose** — clicking "Confirm
Subscription" on the Pricing page doesn't charge anyone. Instead it:

1. Activates the plan in the app immediately, and
2. Sends **you** (the site owner) a notification with the customer's name,
   business, chosen plan, and amount due, so you can follow up by email or
   phone and collect payment (e.g. M-Pesa till/paybill, bank transfer)
   however you already do it.

Every one of these click-events is also always logged inside the app
itself — see **Admin page → Notifications** — even if you never set up
WhatsApp/SMS. So nothing is ever missed even with zero setup.

### Getting notified of new subscriptions on your phone

See the full instructions at the top of `notify.py`. In short, the easiest
free option is **WhatsApp via CallMeBot**:

1. Save `+34 644 59 71 66` as a contact on the WhatsApp you want alerts on.
2. Send that contact the exact message: `I allow callmebot to send me messages`
3. You'll get an API key back within a minute.
4. Add these two lines to your app's Secrets (see Step 4 above):
   ```
   CALLMEBOT_PHONE = "2547XXXXXXXX"
   CALLMEBOT_APIKEY = "123456"
   ```

If you'd rather receive a real SMS (small cost per message), use Africa's
Talking instead — instructions are also in `notify.py`.

## Upload file formats

Column headers don't need to match exactly — the app recognises common
variations automatically (e.g. `Item Code`, `Model`, `Item Group`,
`Cost Price`, `Stock Qty` all work).

**Stock upload** — only a **product name** and **quantity** are required.
Everything else is optional:
- `sku` / `model` / `item code` — falls back to the product name if missing.
- `category` / `item group` — left blank if not supplied.
- `unit_cost` — leave blank (or drop the column entirely) to focus purely
  on quantities; every dashboard and report then switches to quantity-based
  figures instead of stock value.
- `reorder_level` — leave blank and it's **calculated automatically** from
  your sales history (expected demand during your supplier lead time, plus
  a safety buffer you can adjust on the Dashboard).
- `expiry_date` — blank for non-perishables.

Each upload **replaces** the current stock snapshot for that user.

**Sales history upload** — only a **product name** and **quantity sold**
are required.
- `sku` — optional, falls back to product name.
- `sale_date` — optional. If present, it's used for accurate day-by-day
  averaging. If absent, you're asked roughly how many months the file
  covers, and the app averages the totals across that period instead.

Uploads are **appended** to existing history.

Sample templates are downloadable from the Upload Stock and Sales History
pages.

## Multi-Branch module

For businesses with more than one shop. Two upload formats:

- **Branch stock** (long format — one row per branch + item): `branch`,
  product name, quantity required; SKU, category, cost, reorder level and
  expiry date optional, same rules as the single-shop upload.
- **Branch sales** (wide format — one column per branch): product name
  (and optionally SKU) on the left, then a column for each branch's units
  sold, with an optional `Total` column on the right (ignored — recomputed
  from the branch columns). You pick which columns are branches on the
  upload page, and the app unpacks the sheet into the same format used
  everywhere else in the app.

Dashboards and Excel reports are then available **per branch**, or as a
side-by-side comparison across all branches, in the module's own page.

## Security notes for going live

- Passwords are hashed with salted PBKDF2 (stdlib only, no extra
  dependency). Fine for a small tool; consider `bcrypt`/`argon2` for a
  larger deployment.
- Add rate-limiting/lockout on login attempts if you expect public traffic.
- Move the database off local SQLite (see above) before storing real
  customer data at scale.
