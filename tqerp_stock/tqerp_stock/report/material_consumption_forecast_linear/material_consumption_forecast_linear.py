# -*- coding: utf-8 -*-
# Report: Material Consumption Forecast (Linear)
# Description: Linear regression-based time series forecast for material consumption
# Author: ChatGPT (GPT-5)

import frappe
from collections import defaultdict
from dateutil.relativedelta import relativedelta


def execute(filters=None):
	f = frappe._dict(filters or {})
	f.company = f.get("company", "")
	f.warehouse = f.get("warehouse", "")
	f.from_date = f.get("from_date")
	f.to_date = f.get("to_date")
	horizon = int(f.get("horizon") or 3)

	if not (f.from_date and f.to_date):
		frappe.throw("Please set both From Date and To Date.")

	# --- 1️⃣ Aggregate monthly consumption (Issues only)
	rows = frappe.db.sql("""
		SELECT
			sle.item_code,
			DATE_FORMAT(sle.posting_date, '%%Y-%%m-01') AS month_start,
			SUM(-sle.actual_qty) AS qty
		FROM `tabStock Ledger Entry` sle
		WHERE sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND (%(company)s = '' OR sle.company = %(company)s)
		  AND (%(warehouse)s = '' OR sle.warehouse = %(warehouse)s)
		  AND sle.actual_qty < 0
		GROUP BY sle.item_code, month_start
		ORDER BY sle.item_code, month_start
	""", f, as_dict=True)

	# --- 2️⃣ Build month range
	start = frappe.utils.getdate(f.from_date).replace(day=1)
	end = frappe.utils.getdate(f.to_date).replace(day=1)
	months = []
	cur = start
	while cur <= end:
		months.append(cur)
		cur = (cur + relativedelta(months=1)).replace(day=1)

	# --- 3️⃣ Create {item_code: {month: qty}}
	mat = defaultdict(lambda: defaultdict(float))
	for r in rows:
		mat[r.item_code][frappe.utils.getdate(r.month_start)] = float(r.qty or 0.0)

	# --- 4️⃣ Linear regression (OLS)
	def ols_linear_forecast(series, h):
		n = len(series)
		if n == 0:
			return 0.0, 0.0, [0.0] * h

		t = list(range(n))
		sum_t = sum(t)
		sum_y = sum(series)
		sum_t2 = sum(x * x for x in t)
		sum_ty = sum(t[i] * series[i] for i in range(n))
		denom = n * sum_t2 - sum_t * sum_t

		if denom == 0:
			a = series[-1] if series else 0.0
			b = 0.0
		else:
			b = (n * sum_ty - sum_t * sum_y) / denom
			a = (sum_y - b * sum_t) / n

		fc = [max(0.0, a + b * k) for k in range(n, n + h)]
		return a, b, fc

	data = []

	# --- 5️⃣ Compute per-item forecast
	for item_code, month_qty in mat.items():
		y = [float(month_qty.get(m, 0.0)) for m in months]
		if sum(y) == 0:
			continue

		a, b, fc = ols_linear_forecast(y, horizon)
		last_3 = y[-3:] if len(y) >= 3 else y
		avg_3mo = sum(last_3) / max(1, len(last_3))
		next_1 = fc[0] if fc else 0.0
		next_h_sum = sum(fc)

		# --- Get projected stock
		if f.warehouse:
			proj_stock = frappe.db.sql("""
				SELECT SUM(projected_qty) FROM `tabBin`
				WHERE item_code=%s AND warehouse=%s
			""", (item_code, f.warehouse))[0][0] or 0.0
		else:
			proj_stock = frappe.db.sql("""
				SELECT SUM(projected_qty) FROM `tabBin`
				WHERE item_code=%s
			""", (item_code,))[0][0] or 0.0

		suggested_req = max(0.0, next_h_sum - proj_stock)

		data.append({
			"item_code": item_code,
			"hist_from": months[0].strftime("%Y-%m"),
			"hist_to": months[-1].strftime("%Y-%m"),
			"avg3": round(avg_3mo, 3),
			"slope": round(b, 3),
			"fc1": round(next_1, 3),
			"fch": round(next_h_sum, 3),
			"proj_stock": round(proj_stock, 3),
			"suggested_req": round(suggested_req, 3),
		})

	# --- 6️⃣ Sort descending by suggested requirement
	data.sort(key=lambda r: r["suggested_req"], reverse=True)

	# --- 7️⃣ Define columns
	columns = [
		{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": "History From (YYYY-MM)", "fieldname": "hist_from", "fieldtype": "Data", "width": 120},
		{"label": "History To (YYYY-MM)", "fieldname": "hist_to", "fieldtype": "Data", "width": 120},
		{"label": "Avg Last 3 Months", "fieldname": "avg3", "fieldtype": "Float", "width": 140},
		{"label": "Trend (slope/mo)", "fieldname": "slope", "fieldtype": "Float", "width": 120},
		{"label": "Forecast Next Month", "fieldname": "fc1", "fieldtype": "Float", "width": 150},
		{"label": f"Forecast Next {horizon} Mo (Sum)", "fieldname": "fch", "fieldtype": "Float", "width": 180},
		{"label": "Projected Stock", "fieldname": "proj_stock", "fieldtype": "Float", "width": 130},
		{"label": "Suggested Requirement", "fieldname": "suggested_req", "fieldtype": "Float", "width": 170},
	]

	return columns, data
