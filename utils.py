"""
utils.py — inventory analytics: flexible column matching, sales-velocity
calculation, stockouts, overstock, aged stock, short expiry, replenishment
suggestions, demo/sample data, and Excel export.
"""

import re
from io import BytesIO
from datetime import date

import numpy as np
import pandas as pd


# ============================================================
# FLEXIBLE COLUMN MATCHING
# Lets people upload sheets with whatever headers their existing system
# already uses (e.g. "Item Code" instead of "sku", "Item Group" instead
# of "category") without renaming anything first.
# ============================================================

_ALIASES = {
    "branch": ["branch", "branchname", "location", "outlet", "shop", "store", "site"],
    "sku": ["sku", "model", "itemcode", "code", "productcode", "id", "itemnumber"],
    "product_name": ["productname", "itemname", "product", "name", "description", "item", "itemgroupname"],
    "category": ["category", "itemgroup", "group", "productcategory", "itemcategory"],
    "quantity": ["quantity", "qty", "currentstock", "stockqty", "onhand", "stockonhand", "closingstock", "stock"],
    "unit_cost": ["unitcost", "cost", "price", "unitprice", "costprice", "buyingprice"],
    "reorder_level": ["reorderlevel", "reorderpoint", "rol", "minstock", "minimumstock", "reorderqty"],
    "expiry_date": ["expirydate", "expiry", "expdate", "expires", "bestbefore"],
    "quantity_sold": ["quantitysold", "qtysold", "unitssold", "salesqty", "quantity", "qty", "totalsold", "total"],
    "sale_date": ["saledate", "date", "transactiondate", "soldon"],
}


def _clean(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def normalize_columns(df: pd.DataFrame, canonical_names):
    """
    Renames whichever of df's columns match a known alias for each name in
    canonical_names to that canonical name (first match wins). Returns
    (df, found_set) — found_set lists which canonical names were located.
    """
    lookup = {_clean(c): c for c in df.columns}
    rename_map = {}
    found = set()
    for canon in canonical_names:
        for alias in _ALIASES.get(canon, [canon]):
            key = _clean(alias)
            if key in lookup and lookup[key] not in rename_map:
                rename_map[lookup[key]] = canon
                found.add(canon)
                break
    return df.rename(columns=rename_map), found


# ============================================================
# SALES VELOCITY
# ============================================================

def average_daily_sellout(sales_df: pd.DataFrame, months_covered: int = 3, lookback_days: int = 90) -> pd.DataFrame:
    """
    Per-SKU average daily/monthly units sold.
    - If sale_date is present and usable, uses up to the last
      `lookback_days` days (~3 months) of actual dated history.
    - If no usable sale_date exists, assumes the uploaded totals cover
      `months_covered` months (set on the Sales History page) and divides
      accordingly — so a date column is never required.
    """
    cols = ["sku", "product_name", "avg_daily_sales", "avg_monthly_sales", "days_of_history"]
    if sales_df is None or sales_df.empty:
        return pd.DataFrame(columns=cols)

    df = sales_df.copy()
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce").fillna(0)

    has_dates = False
    if "sale_date" in df.columns:
        parsed = pd.to_datetime(df["sale_date"], errors="coerce")
        if parsed.notna().any():
            has_dates = True
            df["sale_date"] = parsed

    if has_dates:
        df = df.dropna(subset=["sale_date"])
        cutoff = df["sale_date"].max() - pd.Timedelta(days=lookback_days)
        recent = df[df["sale_date"] >= cutoff]
        if recent.empty:
            recent = df
        span_days = max((recent["sale_date"].max() - recent["sale_date"].min()).days + 1, 1)
        grouped = recent.groupby(["sku", "product_name"], as_index=False)["quantity_sold"].sum()
        grouped["days_of_history"] = span_days
        grouped["avg_daily_sales"] = (grouped["quantity_sold"] / span_days).round(2)
    else:
        months = max(months_covered, 1)
        grouped = df.groupby(["sku", "product_name"], as_index=False)["quantity_sold"].sum()
        grouped["days_of_history"] = months * 30
        grouped["avg_daily_sales"] = (grouped["quantity_sold"] / (months * 30)).round(2)

    grouped["avg_monthly_sales"] = (grouped["avg_daily_sales"] * 30).round(2)
    return grouped[cols]


# ============================================================
# CORE MASTER VIEW
# ============================================================

def build_master_view(stock_df: pd.DataFrame, sales_df: pd.DataFrame,
                       lead_time_days: int = 7, cover_days: int = 14,
                       expiry_alert_days: int = 30, aged_days: int = 60,
                       safety_buffer_pct: int = 20, months_covered: int = 3):
    """
    Joins current stock with sales velocity and computes every flag used
    across the dashboards. Returns (master_df, has_cost).

    Reorder levels: whatever was uploaded is respected; where it's blank,
    it is calculated automatically from sales history — expected demand
    during the supplier lead time, plus a safety buffer.

    Cost: entirely optional. If no unit_cost was supplied anywhere,
    has_cost is False and callers should hide value-based figures and
    lean on quantity-based ones instead.
    """
    if stock_df is None or stock_df.empty:
        return pd.DataFrame(), False

    velocity = average_daily_sellout(sales_df, months_covered=months_covered)
    df = stock_df.merge(velocity[["sku", "avg_daily_sales", "avg_monthly_sales"]], on="sku", how="left")
    df["avg_daily_sales"] = df["avg_daily_sales"].fillna(0)
    df["avg_monthly_sales"] = df["avg_monthly_sales"].fillna(0)

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    df["unit_cost"] = pd.to_numeric(df.get("unit_cost"), errors="coerce")
    has_cost = bool(df["unit_cost"].notna().any())
    df["stock_value"] = (df["quantity"] * df["unit_cost"].fillna(0)).round(2)

    df["reorder_level"] = pd.to_numeric(df.get("reorder_level"), errors="coerce")
    auto_reorder = (df["avg_daily_sales"] * lead_time_days * (1 + safety_buffer_pct / 100)).round(1)
    df["reorder_level_is_auto"] = df["reorder_level"].isna()
    df["reorder_level"] = df["reorder_level"].where(df["reorder_level"].notna(), auto_reorder)

    df["days_of_cover"] = df.apply(
        lambda r: round(r["quantity"] / r["avg_daily_sales"], 1) if r["avg_daily_sales"] > 0 else np.inf,
        axis=1
    )
    df["suggested_order_qty"] = df.apply(
        lambda r: max(round(r["avg_daily_sales"] * (lead_time_days + cover_days) - r["quantity"], 0), 0)
        if r["avg_daily_sales"] > 0 else 0,
        axis=1
    )

    df["expiry_date_parsed"] = pd.to_datetime(df.get("expiry_date"), errors="coerce")
    today = pd.Timestamp(date.today())
    df["days_to_expiry"] = (df["expiry_date_parsed"] - today).dt.days

    df["uploaded_at_parsed"] = pd.to_datetime(df.get("uploaded_at"), errors="coerce").dt.normalize()
    df["days_since_uploaded"] = (today - df["uploaded_at_parsed"]).dt.days.clip(lower=0)

    df["is_stockout"] = df["quantity"] <= 0
    df["is_low_stock"] = (df["quantity"] > 0) & (df["quantity"] <= df["reorder_level"])
    df["is_overstock"] = (df["avg_daily_sales"] > 0) & (df["days_of_cover"] > (cover_days * 3))
    df["is_aged"] = (df["quantity"] > 0) & ((df["avg_daily_sales"] == 0) | (df["days_of_cover"] > aged_days))
    df["is_short_expiry"] = df["days_to_expiry"].notna() & (df["days_to_expiry"] <= expiry_alert_days)

    if "category" not in df.columns:
        df["category"] = ""
    df["category"] = df["category"].fillna("")

    return df, has_cost


# ============================================================
# REPORTS
# ============================================================

def replenishment_report(master_df: pd.DataFrame) -> pd.DataFrame:
    if master_df.empty:
        return master_df
    out = master_df[(master_df["is_stockout"]) | (master_df["is_low_stock"])].copy()
    out = out.sort_values("suggested_order_qty", ascending=False)
    return out[["sku", "product_name", "category", "quantity", "reorder_level", "reorder_level_is_auto",
                "avg_daily_sales", "avg_monthly_sales", "days_of_cover", "suggested_order_qty"]]


def stockouts_report(master_df: pd.DataFrame) -> pd.DataFrame:
    if master_df.empty:
        return master_df
    out = master_df[master_df["is_stockout"]].copy()
    return out[["sku", "product_name", "category", "quantity", "avg_daily_sales", "avg_monthly_sales", "suggested_order_qty"]]


def overstock_report(master_df: pd.DataFrame, has_cost: bool = True) -> pd.DataFrame:
    if master_df.empty:
        return master_df
    out = master_df[master_df["is_overstock"]].copy()
    out = out.sort_values("days_of_cover", ascending=False)
    cols = ["sku", "product_name", "category", "quantity", "avg_daily_sales", "avg_monthly_sales", "days_of_cover"]
    if has_cost:
        cols.append("stock_value")
    return out[cols]


def aged_stock_report(master_df: pd.DataFrame, has_cost: bool = True) -> pd.DataFrame:
    if master_df.empty:
        return master_df
    out = master_df[master_df["is_aged"]].copy()
    sort_col = "stock_value" if has_cost else "quantity"
    out = out.sort_values(sort_col, ascending=False)
    cols = ["sku", "product_name", "category", "quantity", "avg_daily_sales", "days_since_uploaded"]
    if has_cost:
        cols.append("stock_value")
    return out[cols]


def short_expiry_report(master_df: pd.DataFrame, has_cost: bool = True) -> pd.DataFrame:
    if master_df.empty:
        return master_df
    out = master_df[master_df["is_short_expiry"]].copy()
    out = out.sort_values("days_to_expiry", ascending=True)
    out["expiry_date"] = out["expiry_date_parsed"].dt.date.astype(str)
    cols = ["sku", "product_name", "category", "quantity", "expiry_date", "days_to_expiry"]
    if has_cost:
        cols.append("stock_value")
    return out[cols]


# ============================================================
# EXCEL EXPORT
# ============================================================

def to_excel_bytes(sheets: dict) -> bytes:
    """sheets: {sheet_name: DataFrame}. Returns .xlsx file bytes for st.download_button."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe_name = (name or "Sheet1")[:31]
            (df if df is not None and not df.empty else pd.DataFrame({"info": ["No rows for this report"]})) \
                .to_excel(writer, sheet_name=safe_name, index=False)
    return buffer.getvalue()


# ============================================================
# SAMPLE / DEMO DATA
# ============================================================

def sample_stock_template() -> pd.DataFrame:
    return pd.DataFrame([
        {"sku": "SKU001", "product_name": "Paracetamol 500mg (100s)", "category": "Analgesics",
         "quantity": 40, "unit_cost": 150, "expiry_date": "2026-12-31"},
        {"sku": "SKU002", "product_name": "Amoxicillin 250mg (100s)", "category": "Antibiotics",
         "quantity": 5, "unit_cost": "", "expiry_date": "2026-10-15"},
    ])


def sample_sales_template() -> pd.DataFrame:
    return pd.DataFrame([
        {"sku": "SKU001", "product_name": "Paracetamol 500mg (100s)", "quantity_sold": 8, "sale_date": "2026-09-01"},
        {"sku": "SKU001", "product_name": "Paracetamol 500mg (100s)", "quantity_sold": 5, "sale_date": ""},
        {"sku": "SKU002", "product_name": "Amoxicillin 250mg (100s)", "quantity_sold": 2, "sale_date": ""},
    ])


def sample_branch_stock_template() -> pd.DataFrame:
    return pd.DataFrame([
        {"branch": "Town Branch", "sku": "SKU001", "product_name": "Paracetamol 500mg", "category": "Analgesics", "quantity": 40},
        {"branch": "Town Branch", "sku": "SKU002", "product_name": "Amoxicillin 250mg", "category": "Antibiotics", "quantity": 3},
        {"branch": "Estate Branch", "sku": "SKU001", "product_name": "Paracetamol 500mg", "category": "Analgesics", "quantity": 0},
        {"branch": "Estate Branch", "sku": "SKU002", "product_name": "Amoxicillin 250mg", "category": "Antibiotics", "quantity": 25},
    ])


def sample_branch_sales_template() -> pd.DataFrame:
    return pd.DataFrame([
        {"product_name": "Paracetamol 500mg", "sku": "SKU001", "Town Branch": 24, "Estate Branch": 10, "Total": 34},
        {"product_name": "Amoxicillin 250mg", "sku": "SKU002", "Town Branch": 9, "Estate Branch": 4, "Total": 13},
    ])


def melt_branch_sales(wide_df: pd.DataFrame, branch_cols, product_col, sku_col=None):
    """
    Converts a wide sales sheet (one column per branch) into the long
    format (branch, sku, product_name, quantity_sold) the rest of the app
    expects. Any 'Total' column should already be excluded from
    branch_cols by the caller.
    """
    id_vars = [product_col] + ([sku_col] if sku_col else [])
    long_df = wide_df.melt(id_vars=id_vars, value_vars=branch_cols, var_name="branch", value_name="quantity_sold")
    long_df = long_df.rename(columns={product_col: "product_name"})
    if sku_col:
        long_df = long_df.rename(columns={sku_col: "sku"})
    else:
        long_df["sku"] = long_df["product_name"]
    long_df["quantity_sold"] = pd.to_numeric(long_df["quantity_sold"], errors="coerce").fillna(0)
    long_df["sale_date"] = ""
    return long_df[long_df["quantity_sold"] > 0].reset_index(drop=True)


def sample_demo_data():
    """
    A small, fixed example dataset — a chemist carrying multiple drugs —
    used so the Dashboard is never blank before a user uploads real data.
    It's swapped out automatically the moment real stock exists.
    """
    today = pd.Timestamp(date.today())

    stock_rows = [
        # sku, product_name, category, quantity, unit_cost, expiry_days, uploaded_days_ago
        ("DM001", "Paracetamol 500mg",   "Analgesics",     0,   150, 200, 0),
        ("DM002", "Amoxicillin 250mg",   "Antibiotics",    6,   320,  18, 0),
        ("DM003", "ORS Sachets",         "Rehydration",  500,    20, 400, 0),
        ("DM004", "Vitamin C 1000mg",    "Supplements",   60,   250, 300, 0),
        ("DM005", "Cough Syrup 100ml",   "Cold & Flu",     4,   180,  10, 0),
        ("DM006", "Antacid Tablets",     "Digestive",     30,    90, 500, 0),
        ("DM007", "Insulin Vials",       "Diabetes Care", 12,   900,  25, 0),
        ("DM008", "Adhesive Bandages",   "First Aid",    200,     5,   0, 0),
        ("DM009", "Multivitamin Syrup",  "Supplements",   45,   220, 250, 95),
        ("DM010", "Hand Sanitizer 500ml", "Hygiene",       3,   150,   0, 0),
    ]
    stock = pd.DataFrame([
        {
            "id": i + 1, "user_id": 0, "sku": sku, "product_name": name, "category": cat,
            "quantity": qty, "unit_cost": cost,
            "expiry_date": (today + pd.Timedelta(days=exp)).date().isoformat() if exp else "",
            "uploaded_at": (today - pd.Timedelta(days=up_ago)).isoformat(),
        }
        for i, (sku, name, cat, qty, cost, exp, up_ago) in enumerate(stock_rows)
    ])
    stock["reorder_level"] = None

    velocities = {"DM001": 3.5, "DM002": 1.2, "DM003": 8, "DM004": 1.0, "DM005": 0.9,
                  "DM006": 0.4, "DM007": 0.6, "DM008": 2.0, "DM009": 0.0, "DM010": 0.3}
    names = dict(zip(stock["sku"], stock["product_name"]))

    sales_rows = []
    for day_offset in range(60):
        d = today - pd.Timedelta(days=day_offset)
        for sku, v in velocities.items():
            if v <= 0:
                continue
            qty = max(round(v + np.sin(day_offset / 3) * v * 0.3), 0)
            if qty > 0:
                sales_rows.append({"sku": sku, "product_name": names[sku],
                                    "quantity_sold": qty, "sale_date": d.date().isoformat()})
    sales = pd.DataFrame(sales_rows)
    return stock, sales
