import frappe
from frappe.utils import nowdate, getdate

def get_context(context):
    today = getdate(nowdate())
    
    # Get filter values from request (URL query params)
    filters = frappe.local.form_dict
    selected_warehouse = filters.get("warehouse")
    selected_item_group = filters.get("item_group")

    # Base query
    conditions = ["bin.actual_qty > 0"]

    if selected_warehouse:
        conditions.append("bin.warehouse = %(warehouse)s")
    if selected_item_group:
        conditions.append("i.item_group = %(item_group)s")

    condition_sql = " AND ".join(conditions)
    params = {
        "warehouse": selected_warehouse,
        "item_group": selected_item_group
    }

    batch_data = frappe.db.sql(f"""
        SELECT
            b.name AS batch_no,
            b.item AS item_code,
            i.item_name,
            i.item_group,
            bin.warehouse,
            b.expiry_date,
            b.manufacturing_date,
            bin.actual_qty AS qty
        FROM `tabBatch` b
        INNER JOIN `tabBin` bin ON bin.item_code = b.item
        LEFT JOIN `tabItem` i ON i.name = b.item
        WHERE {condition_sql}
        ORDER BY i.item_name, b.name, bin.warehouse
    """, params, as_dict=True)

    batch_list = []
    total_batches = 0
    expired_count = 0
    expiring_soon_count = 0
    ok_count = 0

    for b in batch_data:
        total_batches += 1
        status = "OK"
        delay_days = 0

        # Fetch item shelf life OR use default 30
        item_shelf_life = frappe.db.get_value("Item", b.item_code, "shelf_life_in_days")
        threshold_days = int(item_shelf_life) if item_shelf_life else 30

        # Expiry logic
        if b.expiry_date:
            diff_days = (b.expiry_date - today).days
            if diff_days < 0:
                status = "Expired"
                delay_days = abs(diff_days)
                expired_count += 1
            elif diff_days <= threshold_days:
                status = "Expiring Soon"
                delay_days = diff_days
                expiring_soon_count += 1

        # QC check overrides other statuses
        qc_exists = frappe.db.exists(
            "Quality Inspection",
            {"reference_name": b.batch_no, "docstatus": 0}
        )
        if qc_exists:
            status = "Under QC"

        # Count OK batches
        if status == "OK":
            ok_count += 1

        batch_list.append({
            "batch_no": b.batch_no,
            "item_code": b.item_code,
            "item_name": b.item_name,
            "item_group": b.item_group,
            "warehouse": b.warehouse,
            "expiry_date": b.expiry_date,
            "manufacturing_date": b.manufacturing_date,
            "qty": b.qty,
            "status": status,
            "delay_days": delay_days,
            "threshold_days": threshold_days
        })

    # Pass data to HTML template
    context.batch_list = batch_list
    context.total_batches = total_batches
    context.expired_count = expired_count
    context.expiring_soon_count = expiring_soon_count
    context.ok_count = ok_count
    context.threshold_days = 30  # default
    context.title = "FEFO Control Dashboard"
    context.selected_warehouse = selected_warehouse
    context.selected_item_group = selected_item_group

    # Fetch list of available warehouses and item groups for filter dropdowns
    context.warehouses = [w.name for w in frappe.get_all("Warehouse", fields=["name"])]
    context.item_groups = [g.name for g in frappe.get_all("Item Group", fields=["name"])]

    return context
