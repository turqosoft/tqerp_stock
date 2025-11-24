frappe.query_reports["Item Forecast Report"] = {
    "filters": [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "forecast_months",
            label: __("Forecast Months"),
            fieldtype: "Int",
            default: 3,
            reqd: 1
        },
        {
            fieldname: "item_group",
            label: __("Item Group"),
            fieldtype: "Link",
            options: "Item Group",
            reqd: 1
            
        },
        
        {
            fieldname: "forecast_algorithm",
            label: __("Forecasting Algorithm"),
            fieldtype: "Select",
            options: [
                "Normal",
                "Linear Regression",
                "ARIMA (Fixed)",
                
            ],
            default: "Normal"
        }
    ],
    onload: function (report) {
        report.page.add_inner_button(__('Apply Forecasting'), function () {
            let item_group = frappe.query_report.get_filter_value("item_group");

            // ✅ Validation only for forecasting button (not report refresh)
            if (!item_group) {
                frappe.msgprint({
                    title: __("Missing Item Group"),
                    message: __("Please select an Item Group before applying forecasting."),
                    indicator: "orange"
                });
                return; // stop forecasting process
            }


            let algorithm = frappe.query_report.get_filter_value("forecast_algorithm");
            

            if (algorithm === "Linear Regression") {
                frappe.msgprint("📈 Applying Linear Regression Forecast...");
                frappe.call({
                    method: "tqerp_stock.tqerp_stock.report.item_forecast_report.item_forecast_linear_regression.apply_linear_regression",
                    args: { filters: report.get_values() },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint("✅ Linear Regression Forecast applied successfully.");
                            console.log("Forecast Data:", r.message);
                        }
                    }
                });
            } 
            else if (algorithm === "ARIMA (Fixed)") {
                frappe.msgprint("🔄 Applying ARIMA (Fixed) Forecast...");
                frappe.call({
                    method: "tqerp_stock.tqerp_stock.report.item_forecast_report.item_forecast_arima.apply_arima_forecast",
                    args: { filters: report.get_values() },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint("✅ ARIMA (Fixed) Forecast applied successfully.");
                            console.log("ARIMA Fixed Forecast Data:", r.message);
                        }
                    }
                });
            }
            
            else {
                frappe.msgprint("Showing Normal Forecast (default logic).");
                frappe.query_report.refresh();
            }
        });
    }
};
