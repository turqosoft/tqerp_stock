// Copyright (c) 2025
// Report: Material Consumption Forecast (Linear)
// Description: Frontend filter setup for linear regression report

frappe.query_reports["Material Consumption Forecast (Linear)"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 0
        },
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
            reqd: 0
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "horizon",
            label: __("Forecast Horizon (Months)"),
            fieldtype: "Int",
            reqd: 0,
            default: 3
        }
    ]
};
