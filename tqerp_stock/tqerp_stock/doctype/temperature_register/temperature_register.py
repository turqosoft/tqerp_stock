import frappe
from frappe.model.document import Document

class TemperatureRegister(Document):
    def before_save(self):
        logged_user = frappe.session.user

        # Loop through child table rows
        for row in self.temperature_log:
            if not row.user:
                row.user = logged_user

    