import frappe
from frappe.utils import flt, getdate

def execute(filters=None):
    if not filters:
        filters = {}
    
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    forecast_months = int(filters.get("forecast_months") or 1)
    item_group = filters.get("item_group")

    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": "Past Consumption", "fieldname": "past_consumption", "fieldtype": "Float", "width": 120},
        {"label": "Average Monthly Consumption", "fieldname": "avg_monthly_consumption", "fieldtype": "Float", "width": 150},
        {"label": "Forecast Quantity", "fieldname": "forecast_qty", "fieldtype": "Float", "width": 130},
        {"label": "Last Purchase Rate", "fieldname": "last_purchase_rate", "fieldtype": "Currency", "width": 120},
        {"label": "Estimated Funds", "fieldname": "estimated_funds", "fieldtype": "Currency", "width": 130}
    ]

    # Fetch items
    item_conditions = "1=1"
    if item_group:
        item_conditions += f" AND item_group='{item_group}'"

    items = frappe.db.sql(f"""
        SELECT name as item_code, item_name
        FROM `tabItem`
        WHERE {item_conditions}
    """, as_dict=True)

    data = []

    for item in items:
        # Calculate past consumption
        past_consumption = flt(frappe.db.sql("""
            SELECT SUM(actual_qty) FROM `tabStock Ledger Entry`
            WHERE item_code=%s
            AND posting_date BETWEEN %s AND %s
        """, (item.item_code, from_date, to_date))[0][0] or 0)

        months = max((getdate(to_date) - getdate(from_date)).days / 30, 1)
        avg_monthly_consumption = flt(past_consumption) / months
        forecast_qty = avg_monthly_consumption * forecast_months

        # Last purchase rate
        last_purchase_rate = flt(frappe.db.sql("""
            SELECT rate FROM `tabPurchase Invoice Item`
            WHERE item_code=%s
            ORDER BY posting_date DESC LIMIT 1
        """, (item.item_code))[0][0] or 0)

        estimated_funds = forecast_qty * last_purchase_rate

        data.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "past_consumption": past_consumption,
            "avg_monthly_consumption": avg_monthly_consumption,
            "forecast_qty": forecast_qty,
            "last_purchase_rate": last_purchase_rate,
            "estimated_funds": estimated_funds
        })

    return columns, data
