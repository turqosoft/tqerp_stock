import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class StockQuarantine(Document):
    def on_submit(self):
        """Automatically create Stock Entry on Submit"""
        if not self.expired_batches:
            frappe.throw("No expired batch items available to move.")

        result = move_to_quarantine(self.expired_batches, self.quarantine_warehouse)

        frappe.msgprint(result.get("message"))


@frappe.whitelist()
def get_expired_batches(quarantine_warehouse=None, source_warehouse=None):
    """Fetch expired batches filtered by Source Warehouse and excluding Quarantine Warehouse"""
    today = nowdate()

    conditions = """
        b.expiry_date IS NOT NULL
        AND b.expiry_date < %(today)s
        AND bin.actual_qty > 0
    """

    params = {
        "today": today
    }

    # Filter by Source Warehouse
    if source_warehouse:
        conditions += " AND bin.warehouse = %(source_warehouse)s"
        params["source_warehouse"] = source_warehouse

    # Exclude Quarantine Warehouse
    if quarantine_warehouse:
        conditions += " AND bin.warehouse != %(quarantine_warehouse)s"
        params["quarantine_warehouse"] = quarantine_warehouse

    query = f"""
        SELECT 
            b.name AS batch_no,
            b.expiry_date,
            b.item AS item_code,
            i.item_name,
            i.stock_uom AS uom,
            bin.warehouse,
            bin.actual_qty AS qty,
            w.company
        FROM `tabBatch` b
        LEFT JOIN `tabItem` i ON i.name = b.item
        INNER JOIN `tabBin` bin ON bin.item_code = b.item
        LEFT JOIN `tabWarehouse` w ON w.name = bin.warehouse
        WHERE {conditions}
        ORDER BY b.expiry_date ASC
    """

    return frappe.db.sql(query, params, as_dict=True)



@frappe.whitelist()
def move_to_quarantine(items, quarantine_warehouse):
    """Move selected items to quarantine warehouse — skip zero-quantity and already transferred batches"""
    import json
 
    if isinstance(items, str):
        items = json.loads(items)
 
    if not items:
        frappe.throw("No items selected for transfer.")
 
    if not quarantine_warehouse:
        frappe.throw("Please set a quarantine warehouse before moving items.")
 
    created_entries = []
    skipped_items = []
 
    # Group valid (qty > 0) items by company
    company_map = frappe._dict()
    for item in items:
        qty = float(item.get("qty") or 0)
        company = item.get("company")
        if qty > 0 and company:
            company_map.setdefault(company, []).append(item)
        else:
            skipped_items.append(item.get("item_code") or "Unknown")
 
    # Create Stock Entry per company
    for company, valid_items in company_map.items():
        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Transfer"
        se.company = company
        se.purpose = "Material Transfer"
        se.posting_date = nowdate()
 
        for item in valid_items:
            existing_qty = frappe.db.sql("""
                SELECT SUM(actual_qty) AS qty
                FROM `tabStock Ledger Entry`
                WHERE item_code=%s AND warehouse=%s AND batch_no=%s
            """, (item.get("item_code"), quarantine_warehouse, item.get("batch_no")), as_dict=True)[0]['qty'] or 0
 
            if existing_qty > 0:
                skipped_items.append(item.get("batch_no"))
                continue
 
            s_warehouse = item.get("warehouse")
            if not s_warehouse:
                skipped_items.append(item.get("batch_no"))
                continue
 
            se.append("items", {
                "item_code": item.get("item_code"),
                "batch_no": item.get("batch_no"),
                "qty": item.get("qty"),
                "uom": item.get("uom"),
                "s_warehouse": s_warehouse,
                "t_warehouse": quarantine_warehouse
            })
 
        if se.items:
            try:
                se.insert(ignore_permissions=True)
                se.submit()
                created_entries.append(se.name)
            except Exception as e:
                frappe.log_error(f"Failed to submit Stock Entry for company {company}: {str(e)}")
                skipped_items.extend([item.get("batch_no") for item in valid_items])
 
    frappe.db.commit()
 
    message = f"✅ Stock Entries created successfully: {', '.join(created_entries)}"
    if skipped_items:
        message += f"<br><br>⚠️ Skipped items: {', '.join(skipped_items)}"
 
    return {
        "stock_entries": created_entries,
        "message": message
    }