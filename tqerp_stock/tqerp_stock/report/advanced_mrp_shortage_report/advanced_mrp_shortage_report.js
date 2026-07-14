// Copyright (c) 2024, Nexgen ERP Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Advanced MRP Shortage Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"fieldname": "sales_order",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order"
		},
		{
			"fieldname": "bom",
			"label": __("BOM"),
			"fieldtype": "Link",
			"options": "BOM",
			"get_query": function() {
				return {
					filters: {
						"is_default": 1
					}
				}
			}
		}
	],
	"tree": true,
	"name_field": "name",
	"parent_field": "parent",
	"initial_depth": 3
};
