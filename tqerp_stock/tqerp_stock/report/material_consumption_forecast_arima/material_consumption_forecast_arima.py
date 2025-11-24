# -*- coding: utf-8 -*-
# Report: Material Consumption Forecast ARIMA
# Requires (optional for ARIMA): pandas, numpy, scipy, statsmodels
# Fallback: simple OLS linear forecast if ARIMA deps missing

import frappe
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import math
import traceback

# Try imports for ARIMA; if missing we'll fallback
HAS_ARIMA = True
try:
    import pandas as pd
    import numpy as np
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except Exception:
    HAS_ARIMA = False

def ols_linear_forecast(series, h):
    # simple dependency-free OLS y = a + b*t, t=0..n-1
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

def adf_pick_d(series, max_d=2, alpha=0.05):
    # pick d using ADF if available, else default d=1 for safety when length>12
    if not HAS_ARIMA:
        return 1 if len(series) >= 12 else 0
    cur = series.dropna()
    d = 0
    while d <= max_d:
        try:
            pval = adfuller(cur, autolag='AIC')[1]
        except Exception:
            return min(d, max_d)
        if pval < alpha:
            return d
        d += 1
        cur = cur.diff().dropna()
    return min(d, max_d)

def fit_arima_series(ts, horizon, pmax=2, qmax=2, seasonal=False, s=12):
    """
    ts: pandas Series indexed by Period/Datetime with frequency
    Returns: dict with order, aic, forecast(series), conf_int (if available)
    If statsmodels not available or fit fails, returns None.
    """
    if not HAS_ARIMA:
        return None

    # ensure frequency
    try:
        ts = ts.asfreq(ts.index.inferred_freq or pd.infer_freq(ts.index))
    except Exception:
        ts = ts.sort_index().asfreq(pd.infer_freq(ts.index) or 'MS')

    # small prefill
    ts = ts.fillna(0)

    # pick d
    d = adf_pick_d(ts)

    best = {"aic": float("inf"), "order": None, "seasonal_order": None, "model": None}
    # conservative grid
    for p in range(0, pmax + 1):
        for q in range(0, qmax + 1):
            if seasonal:
                for P in range(0, 2):  # small range for seasonal P
                    for Q in range(0, 2):
                        try:
                            mod = SARIMAX(ts, order=(p, d, q),
                                          seasonal_order=(P, 0, Q, s),
                                          enforce_stationarity=True, enforce_invertibility=True)
                            res = mod.fit(disp=False)
                            if res.aic < best["aic"]:
                                best = {"aic": res.aic, "order": (p, d, q), "seasonal_order": (P, 0, Q, s), "model": res}
                        except Exception:
                            continue
            else:
                try:
                    mod = SARIMAX(ts, order=(p, d, q), enforce_stationarity=True, enforce_invertibility=True)
                    res = mod.fit(disp=False)
                    if res.aic < best["aic"]:
                        best = {"aic": res.aic, "order": (p, d, q), "seasonal_order": None, "model": res}
                except Exception:
                    continue

    if best["model"] is None:
        return None

    model = best["model"]
    try:
        fc_res = model.get_forecast(steps=horizon)
        mean = fc_res.predicted_mean
        ci = fc_res.conf_int()
    except Exception:
        mean = pd.Series([0.0] * horizon, index=pd.date_range(ts.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq='MS'))
        ci = None

    return {
        "order": best["order"],
        "seasonal_order": best["seasonal_order"],
        "aic": float(best["aic"]),
        "forecast": mean,
        "conf_int": ci,
        "model": model
    }

def execute(filters=None):
    f = frappe._dict(filters or {})
    f.company = f.get("company", "") or ""
    f.warehouse = f.get("warehouse", "") or ""
    f.from_date = f.get("from_date")
    f.to_date = f.get("to_date")
    # horizon = int(f.get("horizon"))

    # ✅--- Horizon validation ---
    raw_horizon = f.get("horizon")

    if raw_horizon in (None, "", "null"):
        frappe.throw("Please enter Forecast Horizon (Months).")

    try:
        horizon = int(raw_horizon)
    except Exception:
        frappe.throw("Forecast Horizon must be a valid number.")

    if horizon <= 0:
        frappe.throw("Forecast Horizon must be greater than zero.")
    pmax = int(f.get("pmax") or 2)
    qmax = int(f.get("qmax") or 2)
    seasonal = bool(f.get("seasonal"))
    seasonal_s = int(f.get("seasonal_period") or 12)

    if not (f.from_date and f.to_date):
        frappe.throw("Please set From Date and To Date.")

    # --- Aggregate monthly consumption (issues only --> positive demand)
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

    # build month range
    start = frappe.utils.getdate(f.from_date).replace(day=1)
    end = frappe.utils.getdate(f.to_date).replace(day=1)
    months = []
    cur = start
    while cur <= end:
        months.append(cur)
        cur = (cur + relativedelta(months=1)).replace(day=1)

    # mat: item_code -> {month: qty}
    mat = defaultdict(lambda: defaultdict(float))
    for r in rows:
        mat[r.item_code][frappe.utils.getdate(r.month_start)] = float(r.qty or 0.0)

    data = []
    # loop items
    for item_code, month_qty in mat.items():
        # build ordered series y
        y = [float(month_qty.get(m, 0.0)) for m in months]
        if sum(y) == 0:
            continue

        # Recent avg last 3 months
        last_3 = y[-3:] if len(y) >= 3 else y
        avg_3mo = sum(last_3) / max(1, len(last_3))

        # If ARIMA available, build pandas series and try fit
        arima_res = None
        used_method = "ARIMA" if HAS_ARIMA else "OLS-Fallback"
        try:
            if HAS_ARIMA:
                # create pandas series indexed by month start
                idx = pd.to_datetime([m.strftime("%Y-%m-01") for m in months])
                ser = pd.Series(y, index=idx)
                # ensure monthly freq
                ser = ser.asfreq('MS').fillna(0)
                ar = fit_arima_series(ser, horizon=horizon, pmax=pmax, qmax=qmax, seasonal=seasonal, s=seasonal_s)
                if ar is not None:
                    arima_res = ar
                else:
                    used_method = "ARIMA-failed->OLS"
            # fallback
            if arima_res is None:
                a, b, fc = ols_linear_forecast(y, horizon)
                # create pandas-like forecast array
                fc_index = None
                arima_res = {
                    "order": (0, 0, 0),
                    "seasonal_order": None,
                    "aic": None,
                    "forecast": fc,
                    "conf_int": None,
                    "model": None
                }
                used_method = "OLS-Fallback"
        except Exception:
            # If anything fails, fallback to OLS
            try:
                a, b, fc = ols_linear_forecast(y, horizon)
                arima_res = {
                    "order": (0, 0, 0),
                    "seasonal_order": None,
                    "aic": None,
                    "forecast": fc,
                    "conf_int": None,
                    "model": None
                }
                used_method = "OLS-Fallback-except"
            except Exception:
                # unrecoverable
                frappe.log_error(traceback.format_exc(), "Material Consumption Forecast ARIMA: item fit failed")
                continue
             # --- Debug log for ARIMA/OLS result
        try:
            frappe.logger().info(f"Item: {item_code}, len(series)={len(y)}, horizon={horizon}, forecast_len={len(arima_res.get('forecast', []))}, method={used_method}")
        except Exception as e:
            frappe.logger().info(f"Debug log failed for item {item_code}: {e}")


        # Extract fc values as list of floats
        if isinstance(arima_res.get("forecast"), (list, tuple)):
            fc_vals = [float(x) for x in arima_res["forecast"]]
        else:
            # pandas Series
            fc_vals = [float(x) for x in arima_res["forecast"].tolist()]

        next_1 = fc_vals[0] if fc_vals else 0.0
        next_h_sum = sum(fc_vals)

        # projected stock
        if f.warehouse:
            proj_stock = frappe.db.sql("""
                SELECT IFNULL(SUM(projected_qty),0) FROM `tabBin`
                WHERE item_code=%s AND warehouse=%s
            """, (item_code, f.warehouse))[0][0] or 0.0
        else:
            proj_stock = frappe.db.sql("""
                SELECT IFNULL(SUM(projected_qty),0) FROM `tabBin`
                WHERE item_code=%s
            """, (item_code,))[0][0] or 0.0

        suggested_req = max(0.0, next_h_sum - proj_stock)

        # model order display
        order_disp = arima_res.get("order")
        if arima_res.get("seasonal_order"):
            order_disp = f"{order_disp} x {arima_res.get('seasonal_order')}"

        data.append({
            "item_code": item_code,
            "hist_from": months[0].strftime("%Y-%m"),
            "hist_to": months[-1].strftime("%Y-%m"),
            "avg3": round(avg_3mo, 3),
            "order": str(order_disp),
            "aic": round(arima_res.get("aic"), 3) if arima_res.get("aic") else None,
            "fc1": round(next_1, 3),
            "fch": round(next_h_sum, 3),
            "proj_stock": round(proj_stock, 3),
            "suggested_req": round(suggested_req, 3)
        })

    # sort by suggested_req
    data.sort(key=lambda r: r.get("suggested_req", 0.0), reverse=True)

    # columns are picked from JSON metadata so return standard (Report system will use)
    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
        {"label": "History From (YYYY-MM)", "fieldname": "hist_from", "fieldtype": "Data", "width": 110},
        {"label": "History To (YYYY-MM)", "fieldname": "hist_to", "fieldtype": "Data", "width": 110},
        {"label": "Recent Avg (last 3)", "fieldname": "avg3", "fieldtype": "Float", "width": 120},
        {"label": "Model Order", "fieldname": "order", "fieldtype": "Data", "width": 140},
        {"label": "AIC", "fieldname": "aic", "fieldtype": "Float", "width": 100},
        {"label": "Forecast Next Month", "fieldname": "fc1", "fieldtype": "Float", "width": 120},
        {"label": "Forecast Next Horizon (Sum)", "fieldname": "fch", "fieldtype": "Float", "width": 160},
        {"label": "Projected Stock", "fieldname": "proj_stock", "fieldtype": "Float", "width": 120},
        {"label": "Suggested Requirement", "fieldname": "suggested_req", "fieldtype": "Float", "width": 140}
    ]

    return columns, data
