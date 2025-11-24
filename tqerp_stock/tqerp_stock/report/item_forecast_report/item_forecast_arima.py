# -*- coding: utf-8 -*-
import frappe
import json
import numpy as np
from statsmodels.tsa.arima.model import ARIMA

@frappe.whitelist()
def apply_arima_forecast(filters=None):
    """Apply ARIMA model forecast for item consumption trends"""

    if isinstance(filters, str):
        filters = json.loads(filters or "{}")
    if not filters:
        filters = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    forecast_months = int(filters.get("forecast_months", 1))
    item_group = filters.get("item_group")
    company = filters.get("company")

    # Base SQL condition
    conditions = ""
    values = [from_date, to_date]

    if item_group and item_group != "All Item Groups":
        conditions += " AND i.item_group = %s"
        values.append(item_group)

    if company:
        conditions += " AND sle.company = %s"
        values.append(company)

    # Fetch items and their past consumption
    data = frappe.db.sql(f"""
        SELECT 
            i.name AS item_code,
            i.item_name,
            IFNULL(SUM(sle.actual_qty), 0) AS past_consumption
        FROM 
            `tabItem` i
        LEFT JOIN 
            `tabStock Ledger Entry` sle ON sle.item_code = i.name
        WHERE 
            sle.posting_date BETWEEN %s AND %s
            {conditions}
        GROUP BY 
            i.name, i.item_name
    """, tuple(values), as_dict=True)

    for d in data:
        item_code = d["item_code"]

        # Monthly consumption data
        monthly_data = frappe.db.sql("""
            SELECT MONTH(posting_date) AS month, SUM(actual_qty)
            FROM `tabStock Ledger Entry`
            WHERE item_code=%s AND posting_date BETWEEN %s AND %s
            GROUP BY MONTH(posting_date)
            ORDER BY MONTH(posting_date)
        """, (item_code, from_date, to_date))

        if not monthly_data or len(monthly_data) < 3:
            d["forecast_qty"] = 0
            continue

        y = np.array([abs(c[1]) for c in monthly_data])

        try:
            # Fit ARIMA model
            model = ARIMA(y, order=(1, 1, 1))
            model_fit = model.fit()

            forecast_values = model_fit.forecast(steps=forecast_months)
            forecast_qty = round(float(np.sum(forecast_values)), 2)

        except Exception as e:
            frappe.log_error(f"ARIMA forecast error for {item_code}: {str(e)}", "Item Forecast ARIMA")
            forecast_qty = 0

        d["forecast_qty"] = forecast_qty

        # Get last purchase rate
        last_purchase_rate = frappe.db.get_value(
            "Purchase Invoice Item",
            {"item_code": item_code},
            "rate",
            order_by="creation desc"
        ) or 0

        d["last_purchase_rate"] = last_purchase_rate
        d["estimated_fund"] = round(forecast_qty * last_purchase_rate, 2)

    return data
