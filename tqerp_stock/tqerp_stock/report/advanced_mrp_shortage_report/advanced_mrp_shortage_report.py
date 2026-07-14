import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
        
    warehouse_cols = set()
    data = get_data(filters, warehouse_cols)
    
    # Sort warehouse columns alphabetically
    sorted_wh_cols = sorted(list(warehouse_cols))
    
    columns = get_columns(sorted_wh_cols)
    
    return columns, data

def get_columns(warehouse_cols):
    cols = [
        {"fieldname": "name", "label": _("Order / Component"), "fieldtype": "Data", "width": 250},
        {"fieldname": "parent", "label": _("Parent"), "fieldtype": "Data", "hidden": 1},
        {"fieldname": "sales_order", "label": _("Sales Order"), "fieldtype": "Link", "options": "Sales Order", "width": 140},
        {"fieldname": "so_date", "label": _("SO Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "so_qty", "label": _("SO Qty"), "fieldtype": "Float", "width": 100},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Data", "width": 140},
        {"fieldname": "delivery_date", "label": _("Delivery Date"), "fieldtype": "Date", "width": 110},
        {"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group", "width": 120},
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "description", "label": _("Description"), "fieldtype": "Data", "width": 150},
        {"fieldname": "brand", "label": _("Brand"), "fieldtype": "Data", "width": 120},
        {"fieldname": "bom_qty", "label": _("BOM Qty"), "fieldtype": "Float", "width": 100},
        {"fieldname": "bom_uom", "label": _("BOM UOM"), "fieldtype": "Data", "width": 100},
        {"fieldname": "pending_qty", "label": _("Required Qty"), "fieldtype": "Float", "width": 110},
        {"fieldname": "stock_qty", "label": _("Available Stock (Global)"), "fieldtype": "Float", "width": 160},
        {"fieldname": "allocated_stock", "label": _("Allocated Stock"), "fieldtype": "Float", "width": 130},
        {"fieldname": "allocated_stock_pcs", "label": _("Allocated Stock (Pcs)"), "fieldtype": "Float", "width": 160},
    ]
    
    # Dynamically inject warehouse columns
    for wh in warehouse_cols:
        cols.append({
            "fieldname": wh,
            "label": _(wh),
            "fieldtype": "Float",
            "width": 120
        })
        
    cols.extend([
        {"fieldname": "po_numbers", "label": _("PO Number"), "fieldtype": "Data", "width": 140},
        {"fieldname": "po_dates", "label": _("PO Date"), "fieldtype": "Data", "width": 110},
        {"fieldname": "po_qty", "label": _("Pending PO Qty (Global)"), "fieldtype": "Float", "width": 160},
        {"fieldname": "allocated_po", "label": _("Allocated PO Qty"), "fieldtype": "Float", "width": 140},
        {"fieldname": "exp_dates", "label": _("Expected Delivery"), "fieldtype": "Data", "width": 130},
        {"fieldname": "suppliers", "label": _("Supplier Name"), "fieldtype": "Data", "width": 150},
        {"fieldname": "net_qty", "label": _("Net Shortage"), "fieldtype": "Float", "width": 110}
    ])
    
    return cols

def get_data(filters, warehouse_cols):
    data = []
    
    query = """
        SELECT
            soi.name as soi_name, soi.parent as sales_order, so.transaction_date as so_date, 
            so.customer, so.delivery_date,
            soi.item_code, soi.item_name, soi.qty, soi.delivered_qty
        FROM
            `tabSales Order Item` soi
        INNER JOIN
            `tabSales Order` so ON soi.parent = so.name
        WHERE
            so.docstatus = 1
            AND so.status NOT IN ('Closed', 'Completed')
            AND soi.qty > soi.delivered_qty
    """
    
    conditions = []
    values = {}
    
    if filters.get("company"):
        conditions.append("so.company = %(company)s")
        values["company"] = filters.get("company")
        
    if filters.get("project"):
        conditions.append("so.project = %(project)s")
        values["project"] = filters.get("project")
        
    if filters.get("sales_order"):
        conditions.append("so.name = %(sales_order)s")
        values["sales_order"] = filters.get("sales_order")
        
    if filters.get("bom"):
        bom_item = frappe.db.get_value("BOM", filters.get("bom"), "item")
        if bom_item:
            conditions.append("soi.item_code = %(bom_item)s")
            values["bom_item"] = bom_item
        
    if conditions:
        query += " AND " + " AND ".join(conditions)
        
    query += " ORDER BY so.delivery_date ASC, soi.parent ASC"
    
    so_items = frappe.db.sql(query, values, as_dict=1)
    
    processed_items = set()
    global_stock_tracker = {}
    global_po_tracker = {}
    
    for row in so_items:
        pending_qty = row.qty - row.delivered_qty
        processed_items.add(row.item_code)
        
        explode_node(
            item_code=row.item_code,
            item_name=row.item_name,
            req_qty=pending_qty,
            parent_node="",
            base_node_name=f"{row.sales_order} | {row.item_code}",
            so_data=row,
            filters=filters,
            data=data,
            warehouse_cols=warehouse_cols,
            bom_qty=1.0,
            bom_uom=None,
            conversion_factor=1.0,
            global_stock_tracker=global_stock_tracker,
            global_po_tracker=global_po_tracker
        )
        
    # HYBRID DEMAND: Fill in Project/BOM Pre-Orders if no SO exists yet
    bom_project_field = "project" if frappe.db.has_column("BOM", "project") else ("custom_project" if frappe.db.has_column("BOM", "custom_project") else None)
    
    fetch_hybrid = False
    bom_conditions = ["is_active = 1", "docstatus = 1"]
    bom_values = {}
    
    if filters.get("project") and bom_project_field:
        bom_conditions.append(f"{bom_project_field} = %(project_bom)s")
        bom_values["project_bom"] = filters.get("project")
        fetch_hybrid = True
        
    if filters.get("bom"):
        bom_conditions.append("name = %(bom_name)s")
        bom_values["bom_name"] = filters.get("bom")
        fetch_hybrid = True
        
    if fetch_hybrid:
        query_bom = "SELECT name, item, quantity FROM `tabBOM` WHERE " + " AND ".join(bom_conditions)
        boms = frappe.db.sql(query_bom, bom_values, as_dict=1)
        
        for bom in boms:
            if bom.item not in processed_items:
                processed_items.add(bom.item)
                item_name = frappe.db.get_value("Item", bom.item, "item_name")
                
                mock_so = frappe._dict({
                    "sales_order": "",
                    "so_date": None,
                    "qty": bom.quantity,
                    "customer": "",
                    "delivery_date": None
                })
                
                explode_node(
                    item_code=bom.item,
                    item_name=item_name,
                    req_qty=bom.quantity,
                    parent_node="",
                    base_node_name=f"Pre-Order BOM | {bom.item}",
                    so_data=mock_so,
                    filters=filters,
                    data=data,
                    warehouse_cols=warehouse_cols,
                    bom_qty=1.0,
                    bom_uom=None,
                    conversion_factor=1.0,
                    global_stock_tracker=global_stock_tracker,
                    global_po_tracker=global_po_tracker
                )
                    
    return data

def explode_node(item_code, item_name, req_qty, parent_node, base_node_name, so_data, filters, data, warehouse_cols, bom_qty, bom_uom, conversion_factor, global_stock_tracker, global_po_tracker):
    item_details = frappe.db.get_value("Item", item_code, ["item_group", "description", "brand", "stock_uom"], as_dict=True) or {}
    
    if not bom_uom:
        bom_uom = item_details.get("stock_uom")
        
    # Initialize trackers if first time seeing this item
    if item_code not in global_stock_tracker:
        total_stock, wh_dict = get_warehouse_stock(item_code)
        global_stock_tracker[item_code] = {
            "total_available": total_stock,
            "allocated": 0,
            "wh_dict": wh_dict
        }
        
    if item_code not in global_po_tracker:
        total_po, po_dates, exp_dates, suppliers, po_numbers = get_pending_po_details(item_code, filters)
        global_po_tracker[item_code] = {
            "total_po": total_po,
            "allocated": 0,
            "po_dates": po_dates,
            "exp_dates": exp_dates,
            "suppliers": suppliers,
            "po_numbers": po_numbers
        }
        
    stock_info = global_stock_tracker[item_code]
    po_info = global_po_tracker[item_code]
    
    # 1. Allocate Stock
    stock_left_to_allocate = stock_info["total_available"] - stock_info["allocated"]
    allocated_stock_to_row = min(req_qty, stock_left_to_allocate)
    if allocated_stock_to_row < 0: allocated_stock_to_row = 0
    stock_info["allocated"] += allocated_stock_to_row
    
    # 2. Remaining Need after stock
    remaining_need = req_qty - allocated_stock_to_row
    if remaining_need < 0: remaining_need = 0
    
    # 3. Allocate PO
    po_left_to_allocate = po_info["total_po"] - po_info["allocated"]
    allocated_po_to_row = min(remaining_need, po_left_to_allocate)
    if allocated_po_to_row < 0: allocated_po_to_row = 0
    po_info["allocated"] += allocated_po_to_row
    
    # 4. Final Net Shortage for this row
    net_qty = remaining_need - allocated_po_to_row
    if net_qty < 0: net_qty = 0
    
    # Calculate stock quantity yield (Pcs) only if BOM UOM is Kg
    if bom_uom and bom_uom.strip().lower() in ['kg', 'kgs']:
        if bom_qty and float(bom_qty) != 0.0:
            allocated_stock_pcs = allocated_stock_to_row / float(bom_qty)
        else:
            allocated_stock_pcs = allocated_stock_to_row
    else:
        allocated_stock_pcs = allocated_stock_to_row
    
    # Collect unique warehouse names to generate columns later
    for wh in stock_info["wh_dict"].keys():
        warehouse_cols.add(wh)
    
    if parent_node == "":
        node_name = base_node_name
    else:
        node_name = f"{parent_node} -> {item_code}"
        
    row_dict = {
        "name": node_name,
        "parent": parent_node,
        "sales_order": so_data.sales_order,
        "so_date": so_data.so_date,
        "so_qty": so_data.qty if parent_node == "" else None,
        "customer": so_data.customer if parent_node == "" else "",
        "delivery_date": so_data.delivery_date if parent_node == "" else None,
        "item_group": item_details.get("item_group"),
        "item_code": item_code,
        "item_name": item_name,
        "description": item_details.get("description"),
        "brand": item_details.get("brand"),
        "bom_qty": bom_qty if parent_node != "" else None,
        "bom_uom": bom_uom,
        "pending_qty": req_qty,
        "stock_qty": stock_info["total_available"],
        "allocated_stock": allocated_stock_to_row,
        "allocated_stock_pcs": allocated_stock_pcs,
        "po_numbers": po_info["po_numbers"],
        "po_dates": po_info["po_dates"],
        "po_qty": po_info["total_po"],
        "allocated_po": allocated_po_to_row,
        "exp_dates": po_info["exp_dates"],
        "suppliers": po_info["suppliers"],
        "net_qty": net_qty
    }
    
    # Dynamically inject warehouse quantities into the row dict (for visibility only, not allocated per WH)
    row_dict.update(stock_info["wh_dict"])
    
    data.append(row_dict)
    
    # Recursive explosion always happens now, passing down the NET requirement (net_qty)
    default_bom = frappe.db.get_value("Item", item_code, "default_bom")
    if default_bom:
        bom_base_qty = frappe.db.get_value("BOM", default_bom, "quantity") or 1.0
        components = frappe.db.get_all(
            "BOM Item", 
            filters={"parent": default_bom}, 
            fields=["item_code", "item_name", "qty as bom_qty", "uom", "conversion_factor"], 
            order_by="idx asc"
        )
        for comp in components:
            # We pass down the net_qty (Net Shortage) as the requirement for the child
            comp_req_qty = (net_qty * comp.bom_qty) / bom_base_qty
            explode_node(
                item_code=comp.item_code,
                item_name=comp.item_name,
                req_qty=comp_req_qty,
                parent_node=node_name,
                base_node_name="",
                so_data=so_data,
                filters=filters,
                data=data,
                warehouse_cols=warehouse_cols,
                bom_qty=comp.bom_qty,
                bom_uom=comp.uom,
                conversion_factor=comp.conversion_factor or 1.0,
                global_stock_tracker=global_stock_tracker,
                global_po_tracker=global_po_tracker
            )

def get_warehouse_stock(item_code):
    bins = frappe.db.sql("""
        SELECT warehouse, actual_qty 
        FROM `tabBin` 
        WHERE item_code = %s AND actual_qty > 0
    """, item_code, as_dict=1)
    
    if not bins:
        return 0, {}
        
    total_qty = sum([b.actual_qty for b in bins])
    wh_dict = {b.warehouse: b.actual_qty for b in bins}
    return total_qty, wh_dict

def get_pending_po_details(item_code, filters):
    query = """
        SELECT 
            po.name as po_name,
            po.transaction_date, 
            poi.schedule_date, 
            po.supplier, 
            (poi.qty - poi.received_qty) as pending_qty
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %(item_code)s
        AND po.docstatus = 1
        AND po.status NOT IN ('Closed', 'Completed')
        AND poi.qty > poi.received_qty
    """
    values = {"item_code": item_code}
    
    if filters.get("company"):
        query += " AND po.company = %(company)s"
        values["company"] = filters.get("company")
        
    if filters.get("project"):
        query += " AND poi.project = %(project)s"
        values["project"] = filters.get("project")
        
    res = frappe.db.sql(query, values, as_dict=1)
    
    if not res:
        return 0, "", "", "", ""
        
    total_po_qty = sum([r.pending_qty for r in res])
    po_dates = ", ".join(list(set([str(r.transaction_date) for r in res if r.transaction_date])))
    exp_dates = ", ".join(list(set([str(r.schedule_date) for r in res if r.schedule_date])))
    suppliers = ", ".join(list(set([r.supplier for r in res if r.supplier])))
    po_numbers = ", ".join(list(set([r.po_name for r in res if r.po_name])))
    
    return total_po_qty, po_dates, exp_dates, suppliers, po_numbers
