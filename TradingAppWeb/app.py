import json
from pathlib import Path
from flask import Flask, render_template, redirect, url_for, abort, request
from data import load_data, fetch_and_cache
from prices import get_price_info

app = Flask(__name__)

COMPANIES_FILE  = Path(__file__).parent / "companies.json"
COMPANY_COLORS  = ["#60a5fa", "#a78bfa", "#4ade80", "#fb923c", "#f472b6"]


def load_companies() -> list[dict]:
    return json.loads(COMPANIES_FILE.read_text())


def company_by_ticker(ticker: str) -> dict | None:
    return next((c for c in load_companies() if c["ticker"] == ticker.upper()), None)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(val, kind="num"):
    if val is None:
        return ""
    if kind == "pct":
        return f"{val * 100:.1f} %"
    if kind in ("eps", "price"):
        return f"{val:,.2f}"
    if kind == "shares":
        return f"{val:,.1f}"
    return f"{val:,.0f}"


def _yoy(series: dict, year: str, all_years_sorted: list) -> float | None:
    idx = all_years_sorted.index(year) if year in all_years_sorted else -1
    if idx <= 0:
        return None
    prev = all_years_sorted[idx - 1]
    v_curr, v_prev = series.get(year), series.get(prev)
    if v_curr is None or v_prev is None or v_prev == 0:
        return None
    return (v_curr / v_prev) - 1


def _margin(num_series: dict, den_series: dict, year: str) -> float | None:
    n, d = num_series.get(year), den_series.get(year)
    if n is None or not d:
        return None
    return n / d


# ---------------------------------------------------------------------------
# Row builders (single-company)
# ---------------------------------------------------------------------------

def _row(label, series, years, kind="num", row_type="normal"):
    return {"label": label, "type": row_type,
            "values": [_fmt(series.get(yr), kind) for yr in years]}

def _pct_row(label, pct_dict, years):
    return {"label": label, "type": "pct",
            "values": [_fmt(pct_dict.get(yr), "pct") for yr in years]}

def _yoy_row(label, series, years, all_sorted):
    return _pct_row(label, {yr: _yoy(series, yr, all_sorted) for yr in years}, years)

def _margin_row(label, num_s, den_s, years):
    return _pct_row(label, {yr: _margin(num_s, den_s, yr) for yr in years}, years)

def _section(label, years):
    return {"label": label, "type": "section", "values": [""] * len(years)}


# ---------------------------------------------------------------------------
# Derived series (shared between single-view and comparison)
# ---------------------------------------------------------------------------

def compute_derived(s: dict, display_years: list) -> dict:
    """Compute all display-ready series from raw XBRL series."""
    neg    = lambda series: {yr: -v for yr, v in series.items() if v is not None}
    neg_nz = lambda series: {yr: -v for yr, v in series.items() if v}

    gross_profit = {
        yr: s["revenues"][yr] - s["cogs"][yr]
        for yr in display_years
        if s["revenues"].get(yr) is not None and s["cogs"].get(yr) is not None
    }
    total_opex = {
        yr: -(gross_profit[yr] - s["operating_income"][yr])
        for yr in display_years
        if gross_profit.get(yr) is not None and s["operating_income"].get(yr) is not None
    }
    ebitda = {
        yr: s["operating_income"][yr] + s["dna"][yr]
        for yr in display_years
        if s["operating_income"].get(yr) is not None and s["dna"].get(yr) is not None
    }
    eff_tax = {
        yr: (s["tax"].get(yr) or 0) / s["pretax_income"][yr]
        for yr in display_years
        if s["pretax_income"].get(yr)
    }
    return {
        "revenues":          s["revenues"],
        "cogs_neg":          neg(s["cogs"]),
        "gross_profit":      gross_profit,
        "sga_neg":           neg(s["sga"]),
        "rd_neg":            neg(s["rd"]),
        "amort_neg":         neg(s["amortization"]),
        "restructuring_neg": neg_nz(s["restructuring"]),
        "goodwill_imp_neg":  neg_nz(s["goodwill_impairment"]),
        "asset_imp_neg":     neg_nz(s["asset_impairment"]),
        "other_opex":        {yr: v for yr, v in s["other_opex"].items() if v},
        "total_opex":        total_opex,
        "operating_income":  s["operating_income"],
        "interest_exp_neg":  neg(s["interest_exp"]),
        "interest_inc":      s["interest_inc"],
        "pretax_income":     s["pretax_income"],
        "tax_neg":           neg(s["tax"]),
        "net_income":        s["net_income"],
        "eps_diluted":       s["eps_diluted"],
        "eps_basic":         s["eps_basic"],
        "shares_diluted":    s["shares_diluted"],
        "shares_basic":      s["shares_basic"],
        "ebitda":            ebitda,
        "rd":                s["rd"],
        "eff_tax":           eff_tax,
    }


# ---------------------------------------------------------------------------
# Single-company table
# ---------------------------------------------------------------------------

def build_table(s: dict, display_years: list, yoy_base: list) -> list:
    d  = compute_derived(s, display_years)
    R  = lambda label, key, **kw:  _row(label, d[key], display_years, **kw)
    YY = lambda label, key:        _yoy_row(label, d[key], display_years, yoy_base)
    M  = lambda label, n, den:     _margin_row(label, d[n], d[den], display_years)
    P  = lambda label, key:        _pct_row(label, d[key], display_years)
    S  = lambda label:             _section(label, display_years)

    return [
        R("Total Revenues",                   "revenues",        row_type="revenue"),
        YY("   % Change YoY",                 "revenues"),
        R("Cost of Goods Sold",               "cogs_neg"),
        R("Gross Profit",                     "gross_profit",    row_type="bold"),
        YY("   % Change YoY",                 "gross_profit"),
        M("   % Gross Margins",               "gross_profit",    "revenues"),
        R("Selling General & Admin Expenses", "sga_neg"),
        R("R&D Expenses",                     "rd_neg"),
        R("Amortization of Intangibles",      "amort_neg"),
        R("Restructuring Charges",            "restructuring_neg"),
        R("Goodwill Impairment",              "goodwill_imp_neg"),
        R("Asset Impairment",                 "asset_imp_neg"),
        R("Other Operating Income (Expense)", "other_opex"),
        R("Total Operating Expenses",         "total_opex",      row_type="bold"),
        R("Operating Income",                 "operating_income",row_type="bold"),
        YY("   % Change YoY",                 "operating_income"),
        M("   % Operating Margins",           "operating_income","revenues"),
        R("Interest Expense",                 "interest_exp_neg"),
        R("Interest And Investment Income",   "interest_inc"),
        R("Pre-tax Income (EBT)",             "pretax_income",   row_type="bold"),
        R("Income Tax Expense",               "tax_neg"),
        R("Net Income",                       "net_income",      row_type="revenue"),
        M("   % Net Income Margins",          "net_income",      "revenues"),
        S("Supplementary Data:"),
        R("Diluted EPS",                      "eps_diluted",     kind="eps", row_type="bold"),
        YY("   % Change YoY",                 "eps_diluted"),
        R("Diluted Shares Outstanding (M)",   "shares_diluted",  kind="shares"),
        R("Basic EPS",                        "eps_basic",       kind="eps"),
        R("Basic Shares Outstanding (M)",     "shares_basic",    kind="shares"),
        R("EBITDA",                           "ebitda",          row_type="bold"),
        YY("   % Change YoY",                 "ebitda"),
        R("R&D Expense",                      "rd"),
        P("Effective Tax Rate %",             "eff_tax"),
    ]


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

# Each entry: (display_label, derived_key, kind, base_row_type)
# kind:  "num" | "eps" | "shares" | "pct" | "yoy" | "margin:<num_key>/<den_key>"
_COMP_METRICS = [
    ("Total Revenues",                   "revenues",         "num",    "revenue"),
    ("   % Change YoY",                  "revenues",         "yoy",    "pct"),
    ("Cost of Goods Sold",               "cogs_neg",         "num",    "normal"),
    ("Gross Profit",                     "gross_profit",     "num",    "bold"),
    ("   % Change YoY",                  "gross_profit",     "yoy",    "pct"),
    ("   % Gross Margins",               "gross_profit",     "margin:gross_profit/revenues", "pct"),
    ("Selling General & Admin Expenses", "sga_neg",          "num",    "normal"),
    ("R&D Expenses",                     "rd_neg",           "num",    "normal"),
    ("Amortization of Intangibles",      "amort_neg",        "num",    "normal"),
    ("Restructuring Charges",            "restructuring_neg","num",    "normal"),
    ("Goodwill Impairment",              "goodwill_imp_neg", "num",    "normal"),
    ("Asset Impairment",                 "asset_imp_neg",    "num",    "normal"),
    ("Other Operating Income (Expense)", "other_opex",       "num",    "normal"),
    ("Total Operating Expenses",         "total_opex",       "num",    "bold"),
    ("Operating Income",                 "operating_income", "num",    "bold"),
    ("   % Change YoY",                  "operating_income", "yoy",    "pct"),
    ("   % Operating Margins",           "operating_income", "margin:operating_income/revenues", "pct"),
    ("Interest Expense",                 "interest_exp_neg", "num",    "normal"),
    ("Interest And Investment Income",   "interest_inc",     "num",    "normal"),
    ("Pre-tax Income (EBT)",             "pretax_income",    "num",    "bold"),
    ("Income Tax Expense",               "tax_neg",          "num",    "normal"),
    ("Net Income",                       "net_income",       "num",    "revenue"),
    ("   % Net Income Margins",          "net_income",       "margin:net_income/revenues", "pct"),
    ("__section__",                      "Supplementary Data:", "", ""),
    ("Diluted EPS",                      "eps_diluted",      "eps",    "bold"),
    ("   % Change YoY",                  "eps_diluted",      "yoy",    "pct"),
    ("Diluted Shares Outstanding (M)",   "shares_diluted",   "shares", "normal"),
    ("Basic EPS",                        "eps_basic",        "eps",    "normal"),
    ("Basic Shares Outstanding (M)",     "shares_basic",     "shares", "normal"),
    ("EBITDA",                           "ebitda",           "num",    "bold"),
    ("   % Change YoY",                  "ebitda",           "yoy",    "pct"),
    ("R&D Expense",                      "rd",               "num",    "normal"),
    ("Effective Tax Rate %",             "eff_tax",          "pct",    "pct"),
]


def build_comparison_table(all_derived: dict, display_years: list, yoy_base: list) -> list:
    """
    all_derived: {ticker: {color, derived_dict}}
    Returns flat list of rows for compare.html.
    Row types: "comp-section" | "comp-metric" | "comp-data" | "comp-pct"
    """
    rows = []

    def _company_values(derived, key, kind):
        if kind == "yoy":
            return [_fmt(_yoy(derived[key], yr, yoy_base), "pct") for yr in display_years]
        if kind.startswith("margin:"):
            num_k, den_k = kind[7:].split("/")
            return [_fmt(_margin(derived[num_k], derived[den_k], yr), "pct") for yr in display_years]
        return [_fmt(derived[key].get(yr), kind) for yr in display_years]

    for label, key, kind, base_type in _COMP_METRICS:
        if label == "__section__":
            rows.append({"type": "comp-section", "label": key, "companies": []})
            continue

        row_kind = "comp-pct" if base_type == "pct" else "comp-data"

        rows.append({"type": "comp-metric", "label": label, "base_type": base_type})
        for ticker, info in all_derived.items():
            rows.append({
                "type":   row_kind,
                "label":  ticker,
                "color":  info["color"],
                "values": _company_values(info["derived"], key, kind),
            })

    return rows


# ---------------------------------------------------------------------------
# Balance sheet table
# ---------------------------------------------------------------------------

def build_balance_sheet_table(s: dict, display_years: list) -> list:
    """Build flat list of row dicts for the Balance Sheet section."""
    neg = lambda key: {yr: -v for yr, v in s.get(key, {}).items() if v is not None}

    def R(label, key, row_type="normal", kind="num"):
        series = s.get(key, {})
        return {"label": label, "type": row_type,
                "values": [_fmt(series.get(yr), kind) for yr in display_years]}

    def R_neg(label, key, row_type="normal"):
        series = neg(key)
        return {"label": label, "type": row_type,
                "values": [_fmt(series.get(yr)) for yr in display_years]}

    def S(label):
        return {"label": label, "type": "section", "values": [""] * len(display_years)}

    return [
        S("Assets"),
        R("Cash And Equivalents",                        "bs_cash"),
        R("Short Term Investments",                      "bs_st_investments"),
        R("Total Cash And Short Term Investments",       "bs_total_cash_st_inv",       "bold"),
        R("Accounts Receivable",                         "bs_accounts_receivable"),
        R("Total Receivables",                           "bs_total_receivables"),
        R("Inventory",                                   "bs_inventory"),
        R("Prepaid Expenses",                            "bs_prepaid_expenses"),
        R("Deferred Tax Assets Current",                 "bs_deferred_tax_curr"),
        R("Other Current Assets",                        "bs_other_current_assets"),
        R("Total Current Assets",                        "bs_total_current_assets",    "bold"),
        R("Gross Property Plant And Equipment",          "bs_gross_ppe"),
        R_neg("Accumulated Depreciation",                "bs_accum_depreciation"),
        R("Net Property Plant And Equipment",            "bs_net_ppe",                 "bold"),
        R("Long-term Investments",                       "bs_lt_investments"),
        R("Goodwill",                                    "bs_goodwill"),
        R("Other Intangibles",                           "bs_other_intangibles"),
        R("Deferred Tax Assets Long-Term",               "bs_deferred_tax_lt"),
        R("Deferred Charges Long-Term",                  "bs_deferred_charges_lt"),
        R("Other Long-Term Assets",                      "bs_other_lt_assets"),
        R("Total Assets",                                "bs_total_assets",            "revenue"),

        S("Liabilities"),
        R("Accounts Payable",                            "bs_accounts_payable"),
        R("Accrued Expenses",                            "bs_accrued_expenses"),
        R("Short-term Borrowings",                       "bs_st_borrowings"),
        R("Current Portion of Long-Term Debt",           "bs_current_ltd"),
        R("Current Portion of Capital Lease Obligations","bs_current_capital_lease"),
        R("Current Income Taxes Payable",                "bs_income_taxes_payable"),
        R("Deferred Tax Liability Current",              "bs_deferred_tax_liab_curr"),
        R("Other Current Liabilities",                   "bs_other_current_liab"),
        R("Total Current Liabilities",                   "bs_total_current_liab",      "bold"),
        R("Long-Term Debt",                              "bs_lt_debt"),
        R("Capital Leases",                              "bs_capital_leases_lt"),
        R("Pension & Other Post Retirement Benefits",    "bs_pension"),
        R("Deferred Tax Liability Non Current",          "bs_deferred_tax_liab_nc"),
        R("Other Non Current Liabilities",               "bs_other_nc_liab"),
        R("Total Liabilities",                           "bs_total_liabilities",       "revenue"),

        S("Equity"),
        R("Common Stock",                                "bs_common_stock"),
        R("Additional Paid In Capital",                  "bs_apic"),
        R("Retained Earnings",                           "bs_retained_earnings"),
        R("Comprehensive Income and Other",              "bs_aoci"),
        R("Total Common Equity",                         "bs_total_common_equity",     "bold"),
        R("Minority Interest",                           "bs_minority_interest"),
        R("Total Equity",                                "bs_total_equity",            "bold"),
        R("Total Liabilities And Equity",                "bs_total_liab_and_equity",   "revenue"),

        S("Supplementary Data:"),
        R("Total Shares Outstanding (M)",                "bs_shares_outstanding",      "normal", "shares"),
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("company_view", ticker=load_companies()[0]["ticker"]))


@app.route("/company/<ticker>")
def company_view(ticker: str):
    companies = load_companies()
    company   = company_by_ticker(ticker)
    if not company:
        abort(404)

    data    = load_data(company["ticker"], company["cik"])
    s       = data["series"]
    fetched = data.get("fetched", "")

    all_sorted    = sorted(set(s["revenues"]) | set(s["net_income"]))
    display_years = all_sorted[-10:]
    yoy_base      = all_sorted[-(min(11, len(all_sorted))):]

    rows       = build_table(s, display_years, yoy_base)
    bs_rows    = build_balance_sheet_table(s, display_years)
    price_info = get_price_info(company["ticker"])

    return render_template(
        "index.html",
        companies=companies,
        current_ticker=company["ticker"],
        company=data["company"],
        fetched=fetched,
        headers=[""] + display_years,
        rows=rows,
        bs_rows=bs_rows,
        price=price_info["price"],
        change_pct=price_info["change_pct"],
    )


@app.route("/compare")
def compare():
    companies     = load_companies()
    tickers_param = request.args.get("tickers", "")
    selected      = [t.strip().upper() for t in tickers_param.split(",") if t.strip()]
    selected      = [t for t in selected if company_by_ticker(t)][:5]

    if len(selected) < 2:
        return redirect(url_for("index"))

    # Gather data for each selected company
    all_years = set()
    company_data = {}
    for i, ticker in enumerate(selected):
        c    = company_by_ticker(ticker)
        data = load_data(c["ticker"], c["cik"])
        s    = data["series"]
        all_years |= set(s["revenues"]) | set(s["net_income"])
        company_data[ticker] = {"name": data["company"], "color": COMPANY_COLORS[i], "series": s}

    display_years = sorted(all_years)[-10:]
    yoy_base      = sorted(all_years)[-(min(11, len(all_years))):]

    all_derived = {
        ticker: {
            "color":   info["color"],
            "name":    info["name"],
            "derived": compute_derived(info["series"], display_years),
        }
        for ticker, info in company_data.items()
    }

    comp_rows  = build_comparison_table(all_derived, display_years, yoy_base)
    price_data = {t: get_price_info(t) for t in selected}

    return render_template(
        "compare.html",
        companies=companies,
        selected=selected,
        company_info=all_derived,
        headers=[""] + display_years,
        rows=comp_rows,
        price_data=price_data,
        tickers_param=",".join(selected),
    )


@app.route("/refresh/<ticker>")
def refresh(ticker: str):
    company = company_by_ticker(ticker)
    if not company:
        abort(404)
    fetch_and_cache(company["ticker"], company["cik"])
    return redirect(url_for("company_view", ticker=ticker))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
