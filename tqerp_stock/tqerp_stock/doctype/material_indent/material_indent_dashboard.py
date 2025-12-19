from frappe import _

def get_data():
    return {
        "heatmap": False,
        "fieldname": "material_indent",
        "transactions": [
            {
                "label": _("Stock"),
                "items": ["Stock Entry"]
            }
        ]
    }
