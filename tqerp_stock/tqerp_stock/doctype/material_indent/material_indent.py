# Copyright (c) 2025, turqosoft and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import getdate 


class MaterialIndent(Document):
    pass


@frappe.whitelist()
def get_stock_entry_data(indent_names):
    indent_names = frappe.parse_json(indent_names)
    conversion_factor = 1.0

    material_indents = [
        frappe.get_doc("Material Indent", name)
        for name in indent_names
    ]

    rows = []

    for mi in material_indents:
        if mi.status not in ("Not Processed", "Ordered"):
            frappe.throw(
                f"Material Indent {mi.name} cannot be transferred (Status: {mi.status})"
            )

        rows.append({
            "material_indent": mi.name,
            "item_code": mi.item,
            "item_name": mi.item_name,
            "qty": mi.quantity,
            "uom": mi.uom,
            "conversion_factor": conversion_factor,
            "s_warehouse": mi.source_warehouse,
            "t_warehouse": mi.target_warehouse
        })

    return {"items": rows}



@frappe.whitelist()
def get_indent_data(indent_names):
    indent_names = frappe.parse_json(indent_names)

    material_indents = [
        frappe.get_doc("Material Indent", name)
        for name in indent_names
    ]

    item_map = {}

    for mi in material_indents:
        key = (mi.item, mi.uom, mi.target_warehouse)

        if key not in item_map:
            item_map[key] = {
                "item_code": mi.item,
                "item_name": mi.item_name,
                "uom": mi.uom,
                "target_warehouse": mi.target_warehouse,
                "schedule_date": mi.schedule_date or getdate(),
                "total_qty": 0,
                "material_indents": []
            }

        item_map[key]["total_qty"] += mi.quantity
        item_map[key]["material_indents"].append(mi.name)

    return {
        "items": [
            {
                **data,
                "material_indents": ", ".join(data["material_indents"])
            }
            for data in item_map.values()
        ]
    }


# Update Material Indent Status on Submit of Purchase Order
@frappe.whitelist()
def update_material_indent_status_on_submit(doc, method=None, status="Ordered"):
    for item in doc.items:
        if not item.material_indents:
            continue

        indent_names = [i.strip() for i in item.material_indents.split(",")]

        for name in indent_names:
            frappe.db.set_value("Material Indent", name, "status", status)


# Update Material Indent Status on Cancel of Purchase Order
@frappe.whitelist()
def update_material_indent_status_on_cancel(doc, method=None, status="Cancelled"):
    for item in doc.items:
        if not item.material_indents:
            continue

        indent_names = [i.strip() for i in item.material_indents.split(",")]

        for name in indent_names:
            frappe.db.set_value("Material Indent", name, "status", status)

@frappe.whitelist()
def update_material_indent_status(doc, method=None, status="Processing"):
    for item in doc.items:
        if not item.material_indents:
            continue

        indent_names = [i.strip() for i in item.material_indents.split(",")]

        for name in indent_names:
            frappe.db.set_value("Material Indent", name, "status", status)



@frappe.whitelist()
def on_submit_stock_entry(doc, method=None):
    if doc.stock_entry_type != "Material Transfer":
        return

    for item in doc.items:
        if not item.material_indent:
            continue

        mi = frappe.get_doc("Material Indent", item.material_indent)
        if item.qty >= mi.quantity:
            mi.status = "Transferred"
            mi.received_quantity = item.qty
            mi.save()
        else: 
            mi.status = "Partially Transferred"
            mi.received_quantity = item.qty
            mi.save()

     


@frappe.whitelist()
def on_cancel_stock_entry(doc, method=None):
    if doc.stock_entry_type != "Material Transfer":
        return

    for item in doc.items:
        if not item.material_indent:
            continue

        mi = frappe.get_doc("Material Indent", item.material_indent)
        mi.status = "Cancelled"
        mi.received_quantity = 0
        mi.save()



@frappe.whitelist()
def update_indent_status_on_stock_entry(doc, method=None):
    if doc.stock_entry_type != "Material Transfer":
        return

    for item in doc.items:
        if not item.material_indent:
            continue

        mi = frappe.get_doc("Material Indent", item.material_indent)
        mi.status = "Transferring"
        mi.received_quantity = 0
        mi.save()

     