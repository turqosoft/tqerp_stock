frappe.query_reports["Material Consumption Forecast ARIMA"] = {
    filters: [
      {
        fieldname: "company",
        label: __("Company"),
        fieldtype: "Link",
        options: "Company"
      },
      {
        fieldname: "warehouse",
        label: __("Warehouse"),
        fieldtype: "Link",
        options: "Warehouse"
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
      
      },
      {
        fieldname: "pmax",
        label: __("AR max (p_max)"),
        fieldtype: "Int",
        default: 2
      },
      {
        fieldname: "qmax",
        label: __("MA max (q_max)"),
        fieldtype: "Int",
        default: 2
      },
      {
        fieldname: "seasonal",
        label: __("Use Seasonal (SARIMA)"),
        fieldtype: "Check",
        default: 0
      },
      {
        fieldname: "seasonal_period",
        label: __("Seasonal Period (s)"),
        fieldtype: "Int",
        default: 12
      }
    ]
  };
  