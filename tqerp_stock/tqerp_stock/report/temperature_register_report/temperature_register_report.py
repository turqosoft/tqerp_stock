import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    warehouse = filters.get("warehouse")

    if not from_date or not to_date:
        frappe.throw("From Date and To Date are required")

    # Base SQL Conditions
    conditions = "tri.time BETWEEN %(from_date)s AND %(to_date)s"
    if warehouse:
        conditions += " AND tri.warehouse = %(warehouse)s"

    # Query Temperature Log + Warehouse Min/Max Temperature
    raw_data = frappe.db.sql(f"""
        SELECT
            tri.time,
            tri.warehouse,
            tri.temperature,
            tri.user,
            w.min_temperature,
            w.max_temperature
        FROM
            `tabTemperature Register Item` tri
        LEFT JOIN
            `tabWarehouse` w ON w.name = tri.warehouse
        WHERE
            {conditions}
        ORDER BY
            tri.time ASC
    """, {
        "from_date": from_date,
        "to_date": to_date,
        "warehouse": warehouse
    }, as_dict=True)

    # Apply color formatting for out-of-range temperatures 
    data = []
    for row in raw_data:
        temp = row.temperature
        min_t = row.min_temperature
        max_t = row.max_temperature

        # Check if temperature is out of range
        if min_t is not None and max_t is not None and (temp < min_t or temp > max_t):
            # Cell background red, text black, bold
            temp_html = f"<div style='background-color:red; color:white; font-weight:bold; padding:3px'>{temp}</div>"
        else:
            temp_html = f"{temp}"

        data.append({
            "time": row.time,
            "warehouse": row.warehouse,
            "temperature": temp_html,
            "min_temperature": row.min_temperature,
            "max_temperature": row.max_temperature,
            "user": row.user
        })

    # Report Columns
    columns = [
        {"label": "Time", "fieldname": "time", "fieldtype": "Datetime", "width": 200},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
        {"label": "Temperature (°C)", "fieldname": "temperature", "fieldtype": "Data", "width": 200},
        {"label": "Minimum Temperature (°C)", "fieldname": "min_temperature", "fieldtype": "Float", "width": 200},
        {"label": "Maximum Temperature (°C)", "fieldname": "max_temperature", "fieldtype": "Float", "width": 200},
        {"label": "User", "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 200},
    ]

    return columns, data
