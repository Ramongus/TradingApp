import json
from pathlib import Path
from flask import Flask, render_template, redirect, url_for, abort
from data import load_data, fetch_and_cache
from prices import get_price_info

app = Flask(__name__)

COMPANIES_FILE = Path(__file__).parent / "companies.json"


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
# Row builders
# ---------------------------------------------------------------------------

def _row(label, series, years, kind="num", row_type="normal"):
    return {
        "label":  label,
        "type":   row_type,
        "values": [_fmt(series.get(yr), kind) for yr in years],
    }


def _pct_row(label, pct_dict, years):
    return {
        "label":  label,
        "type":   "pct",
        "values": [_fmt(pct_dict.get(yr), "pct") for yr in years],
    }


def _yoy_row(label, series, years, all_sorted):
    yoy = {yr: _yoy(series, yr, all_sorted) for yr in years}
    return _pct_row(label, yoy, years)


def _margin_row(label, num_s, den_s, years):
    margins = {yr: _margin(num_s, den_s, yr) for yr in years}
    return _pct_row(label, margins, years)


def _section(label, years):
    return {"label": label, "type": "section", "values": [""] * len(years)}


# ---------------------------------------------------------------------------
# Table builder
# ---------------------------------------------------------------------------

def build_table(s: dict, display_years: list, yoy_base: list) -> list:
    neg      = lambda series: {yr: -v for yr, v in series.items() if v is not None}
    neg_nz   = lambda series: {yr: -v for yr, v in series.items() if v}   # skips None and 0

    cogs_neg          = neg(s["cogs"])
    sga_neg           = neg(s["sga"])
    rd_neg            = neg(s["rd"])
    amort_neg         = neg(s["amortization"])
    restructuring_neg = neg_nz(s["restructuring"])
    goodwill_imp_neg  = neg_nz(s["goodwill_impairment"])
    asset_imp_neg     = neg_nz(s["asset_impairment"])
    # other_opex is already net (can be positive or negative), skip zeros
    other_opex        = {yr: v for yr, v in s["other_opex"].items() if v}
    int_exp_neg       = neg(s["interest_exp"])
    tax_neg           = neg(s["tax"])

    gross_profit = {
        yr: s["revenues"][yr] - s["cogs"][yr]
        for yr in display_years
        if s["revenues"].get(yr) is not None and s["cogs"].get(yr) is not None
    }

    # Total OpEx = Gross Profit - Operating Income  (exact, no rounding gaps)
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

    R  = lambda label, series, **kw: _row(label, series, display_years, **kw)
    P  = lambda label, d:            _pct_row(label, d, display_years)
    YY = lambda label, series:       _yoy_row(label, series, display_years, yoy_base)
    M  = lambda label, n, d:         _margin_row(label, n, d, display_years)
    S  = lambda label:               _section(label, display_years)

    return [
        R("Total Revenues",                   s["revenues"],         row_type="revenue"),
        YY("   % Change YoY",                 s["revenues"]),
        R("Cost of Goods Sold",               cogs_neg),
        R("Gross Profit",                     gross_profit,          row_type="bold"),
        YY("   % Change YoY",                 gross_profit),
        M("   % Gross Margins",               gross_profit,          s["revenues"]),
        R("Selling General & Admin Expenses", sga_neg),
        R("R&D Expenses",                     rd_neg),
        R("Amortization of Intangibles",      amort_neg),
        R("Restructuring Charges",            restructuring_neg),
        R("Goodwill Impairment",              goodwill_imp_neg),
        R("Asset Impairment",                 asset_imp_neg),
        R("Other Operating Income (Expense)", other_opex),
        R("Total Operating Expenses",         total_opex,            row_type="bold"),
        R("Operating Income",                 s["operating_income"], row_type="bold"),
        YY("   % Change YoY",                 s["operating_income"]),
        M("   % Operating Margins",           s["operating_income"], s["revenues"]),
        R("Interest Expense",                 int_exp_neg),
        R("Interest And Investment Income",   s["interest_inc"]),
        R("Pre-tax Income (EBT)",             s["pretax_income"],    row_type="bold"),
        R("Income Tax Expense",               tax_neg),
        R("Net Income",                       s["net_income"],       row_type="revenue"),
        M("   % Net Income Margins",          s["net_income"],       s["revenues"]),
        S("Supplementary Data:"),
        R("Diluted EPS",                      s["eps_diluted"],      kind="eps", row_type="bold"),
        YY("   % Change YoY",                 s["eps_diluted"]),
        R("Diluted Shares Outstanding (M)",   s["shares_diluted"],   kind="shares"),
        R("Basic EPS",                        s["eps_basic"],        kind="eps"),
        R("Basic Shares Outstanding (M)",     s["shares_basic"],     kind="shares"),
        R("EBITDA",                           ebitda,                row_type="bold"),
        YY("   % Change YoY",                 ebitda),
        R("R&D Expense",                      s["rd"]),
        P("Effective Tax Rate %",             eff_tax),
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    companies = load_companies()
    return redirect(url_for("company_view", ticker=companies[0]["ticker"]))


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
    price_info = get_price_info(company["ticker"])

    return render_template(
        "index.html",
        companies=companies,
        current_ticker=company["ticker"],
        company=data["company"],
        fetched=fetched,
        headers=[""] + display_years,
        rows=rows,
        price=price_info["price"],
        change_pct=price_info["change_pct"],
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
