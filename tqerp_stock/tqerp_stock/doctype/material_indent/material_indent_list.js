frappe.listview_settings["Material Indent"] = {



    add_fields: ["status"],

    get_indicator: function (doc) {
        if (doc.status === "Not Processed") {
            return [__("Not Processed"), "yellow", "status,=,Not Processed"];
        }
        if (doc.status === "Processing") {
            return [__("Processing"), "orange", "status,=,Processing"];
        }
        if (doc.status === "Ordered") {
            return [__("Ordered"), "blue", "status,=,Ordered"];
        }
        if (doc.status === "Transferred") {
            return [__("Transferred"), "green", "status,=,Transferred"];
        }
        if (doc.status === "Transferring") {
            return [__("Transferring"), "orange", "status,=,Transferring"];
        }
        if (doc.status === "Partially Transferred") {
            return [__("Partially Transferred"), "yellow", "status,=,Partially Transferred"];
        }
        if (doc.status === "Closed") {
            return [__("Closed"), "gray", "status,=,Closed"];
        }   
        if (doc.status === "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"];
        }
    },
    onload(listview) {

        // -------------------------
        // Create Purchase Order
        // -------------------------
        listview.page.add_actions_menu_item(
            __("Create Purchase Order"),
            async () => {
                const selected = listview.get_checked_items();
                if (!selected.length) {
                    frappe.msgprint("Select at least one Material Indent.");
                    return;
                }

                // Allow only Not Processed
                const invalid = selected.filter(d => d.status !== "Not Processed");
                if (invalid.length) {
                    frappe.msgprint({
                        title: __("Action Not Allowed"),
                        indicator: "red",
                        message: __(
                            "Purchase Order can be created only for Material Indents with status <b>Not Processed</b>."
                        )
                    });
                    return;
                }

                const result = await frappe.call({
                    method: "tqerp_stock.tqerp_stock.doctype.material_indent.material_indent.get_indent_data",
                    args: {
                        indent_names: selected.map(d => d.name)
                    }
                });

                const items = result.message.items;

                frappe.model.with_doctype("Purchase Order", () => {
                    let po = frappe.model.get_new_doc("Purchase Order");

                    po.company = frappe.boot.sysdefaults.company;
                    po.items = [];

                    items.forEach(data => {
                        let row = frappe.model.add_child(po, "items");

                        row.item_code = data.item_code;
                        row.item_name = data.item_name;
                        row.qty = data.total_qty;
                        row.uom = data.uom;

                        row.schedule_date = data.schedule_date;
                        row.warehouse = data.target_warehouse;


                        row.material_indents = data.material_indents;
                    });

                    frappe.set_route("Form", "Purchase Order", po.name);
                });
            },
            false,
            __("Create")
        );






        // -------------------------
        // Create Stock Entry (Material Transfer)
        // -------------------------
        listview.page.add_actions_menu_item(
            __("Create Stock Entry (Material Transfer)"),
            async () => {
                const selected = listview.get_checked_items();
                if (!selected.length) {
                    frappe.msgprint("Select at least one Material Indent.");
                    return;
                }

                const result = await frappe.call({
                    method: "tqerp_stock.tqerp_stock.doctype.material_indent.material_indent.get_stock_entry_data",
                    args: {
                        indent_names: selected.map(d => d.name)
                    }
                });

                const items = result.message.items;

                frappe.model.with_doctype("Stock Entry", () => {
                    let se = frappe.model.get_new_doc("Stock Entry");

                    se.stock_entry_type = "Material Transfer";
                    se.items = [];

                    items.forEach(data => {
                        let row = frappe.model.add_child(se, "items");

                        row.item_code = data.item_code;
                        row.item_name = data.item_name;
                        row.qty = data.qty;
                        row.uom = data.uom;
                        row.stock_uom = data.uom;
                        row.conversion_factor = data.conversion_factor;
                        row.transfer_qty = data.qty;
                        row.s_warehouse = data.s_warehouse;
                        row.t_warehouse = data.t_warehouse;

                        // ✅ Link each row to ONE Material Indent
                        row.material_indent = data.material_indent;
                    });

                    frappe.set_route("Form", "Stock Entry", se.name);
                });
            },
            false,
            __("Create")
        );


    }
};
