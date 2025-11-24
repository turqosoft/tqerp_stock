import frappe
import json
import numpy as np
from sklearn.linear_model import LinearRegression

@frappe.whitelist()
def apply_linear_regression(filters=None):
    """Apply true Linear Regression-based consumption forecast"""

    # Ensure filters is a dict
    if isinstance(filters, str):
        filters = json.loads(filters or "{}")
    if not filters:
        filters = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    forecast_months = int(filters.get("forecast_months", 1))
    item_group = filters.get("item_group")
    company = filters.get("company")

    # --- Dynamic conditions ---
    conditions = ""
    values = [from_date, to_date]

    if item_group and item_group != "All Item Groups":
        conditions += " AND i.item_group = %s"
        values.append(item_group)

    if company:
        conditions += " AND sle.company = %s"
        values.append(company)

    # --- Fetch base data (items + past consumption) ---
    data = frappe.db.sql(f"""
        SELECT 
            i.name AS item_code,
            i.item_name,
            ABS(IFNULL(SUM(sle.actual_qty), 0)) AS past_consumption
        FROM 
            `tabItem` i
        LEFT JOIN 
            `tabStock Ledger Entry` sle ON sle.item_code = i.name
        WHERE 
            sle.posting_date BETWEEN %s AND %s
            AND sle.actual_qty < 0
            {conditions}
        GROUP BY 
            i.name, i.item_name
    """, tuple(values), as_dict=True)

    for d in data:
        item_code = d["item_code"]

        # --- Get monthly consumption data ---
        monthly_data = frappe.db.sql("""
            SELECT MONTH(posting_date) AS month, ABS(SUM(actual_qty)) AS qty
            FROM `tabStock Ledger Entry`
            WHERE item_code=%s 
              AND posting_date BETWEEN %s AND %s
              AND actual_qty < 0
            GROUP BY MONTH(posting_date)
            ORDER BY MONTH(posting_date)
        """, (item_code, from_date, to_date))

        if not monthly_data or len(monthly_data) < 2:
            # Not enough data to perform regression
            d["forecast_qty"] = 0
            d["last_purchase_rate"] = 0
            d["estimated_fund"] = 0
            continue

        # --- Prepare regression inputs ---
        x = np.arange(1, len(monthly_data) + 1).reshape(-1, 1)   # Time index (1, 2, 3...)
        y = np.array([m[1] for m in monthly_data])               # Monthly consumption values

        # --- Fit regression model ---
        model = LinearRegression()
        model.fit(x, y)

        # --- Predict next N months ---
        future_x = np.arange(len(monthly_data) + 1, len(monthly_data) + 1 + forecast_months).reshape(-1, 1)
        forecast_values = model.predict(future_x)

        # --- Ensure no negative predictions ---
        forecast_values = np.clip(forecast_values, 0, None)

        # --- Sum of forecasted months ---
        forecast_qty = round(float(np.sum(forecast_values)), 2)
        d["forecast_qty"] = forecast_qty

        # --- Last purchase rate ---
        last_purchase_rate = frappe.db.get_value(
            "Purchase Invoice Item",
            {"item_code": item_code},
            "rate",
            order_by="creation desc"
        ) or 0

        d["last_purchase_rate"] = last_purchase_rate
        d["estimated_fund"] = round(forecast_qty * last_purchase_rate, 2)

    return data
