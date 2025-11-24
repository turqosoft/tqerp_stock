frappe.ui.form.on("Temperature Register", {
    refresh(frm) {
        frm.fields_dict.temperature_log.grid.get_field("user").read_only = 1;
    }
});

frappe.ui.form.on("Temperature Register Item", {
    temperature_log_add(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);

        // set logged-in user immediately
        frappe.model.set_value(cdt, cdn, "user", frappe.session.user);

        frm.refresh_field("temperature_log");
    }
});

