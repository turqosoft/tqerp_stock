frappe.ui.form.on("Stock Quarantine", {
    refresh: function(frm) {

        // Button → Fetch Expired Batches
        frm.add_custom_button(__('Get Expired Batches'), function() {
            frm.trigger("get_expired_batches");
        });

        // Auto-fill Default Quarantine Warehouse
        if (!frm.doc.quarantine_warehouse) {
            frappe.db.get_single_value("Stock Settings", "default_quarantine_warehouse")
                .then(value => {
                    if (value) {
                        frm.set_value("quarantine_warehouse", value);
                    } else {
                        frappe.msgprint(__('Please set a Default Quarantine Warehouse in Stock Settings.'));
                    }
                });
        }

        // ERPNext Batch Dropdown Formatter 
        frm.fields_dict["expired_batches"].grid.get_field("batch_no").get_query =
            function(doc, cdt, cdn) {

                let row = locals[cdt][cdn];

                return {
                    query: "erpnext.controllers.queries.get_batch_no",
                    filters: {
                        item_code: row.item_code,
                        warehouse: row.warehouse,
                        include_expired_batches: 1
                    }
                };
            };
    },

    // Fetch expired batches (Filtered by Source Warehouse + excluding Quarantine Warehouse)
    get_expired_batches: function(frm) {
        frappe.call({
            method: "tqerp_stock.tqerp_stock.doctype.stock_quarantine.stock_quarantine.get_expired_batches",
            args: {
                quarantine_warehouse: frm.doc.quarantine_warehouse,
                source_warehouse: frm.doc.source_warehouse
            },
            callback: function(r) {
                frm.clear_table("expired_batches");

                if (r.message && r.message.length) {
                    r.message.forEach(function(d) {
                        let row = frm.add_child("expired_batches");
                        row.item_code = d.item_code;
                        row.item_name = d.item_name;
                        row.batch_no = d.batch_no;
                        row.expiry_date = d.expiry_date;
                        row.warehouse = d.warehouse;
                        row.company = d.company;
                        row.qty = d.qty;
                        row.uom = d.uom;
                    });

                    frm.refresh_field("expired_batches");
                    frappe.msgprint(__("Expired batch items fetched successfully."));
                } else {
                    frappe.msgprint(__("No expired batch items found."));
                }
            }
        });
    }
});
