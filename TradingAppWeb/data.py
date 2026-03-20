"""
Fetches income statement data from the SEC EDGAR XBRL API for any company.
Free, no API key required. Data is cached per company to cache_{ticker}.json for the current day.
"""

import json
import requests
from datetime import date
from pathlib import Path

CACHE_DIR = Path(__file__).parent
HEADERS   = {"User-Agent": "TradingAppWeb research@tradingapp.com"}


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"cache_{ticker.upper()}.json"


def _fetch_raw(cik: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _annual(facts: dict, *concepts, unit: str = "USD", divisor: float = 1e6) -> dict:
    """
    Merge 10-K FY data across all concepts. For overlapping years the FIRST
    concept listed takes priority (list the most authoritative concept first).
    Values are divided by `divisor` (default: millions).
    """
    annual: dict[str, tuple] = {}
    # Process in reverse so that the first concept overwrites later ones
    for concept in reversed(concepts):
        entries = facts.get(concept, {}).get("units", {}).get(unit, [])
        for e in entries:
            if e.get("form") in ("10-K", "10-K/A") and e.get("fp") == "FY":
                yr = e["end"][:4]
                if yr not in annual or e["filed"] > annual[yr][1]:
                    annual[yr] = (e["val"], e["filed"])
    return {yr: v[0] / divisor for yr, v in sorted(annual.items())} if annual else {}


def fetch_and_cache(ticker: str, cik: str) -> dict:
    """Force a fresh fetch from SEC EDGAR, overwrite cache, return result."""
    raw  = _fetch_raw(cik)
    g    = raw["facts"].get("us-gaap", {})
    name = raw.get("entityName", ticker)

    series = {
        "revenues":         _annual(g, "RevenueFromContractWithCustomerExcludingAssessedTax",
                                       "Revenues", "SalesRevenueNet"),
        "cogs":             _annual(g, "CostOfGoodsAndServicesSold",
                                       "CostOfRevenue", "CostOfGoodsSold",
                                       "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"),
        "sga":              _annual(g, "SellingGeneralAndAdministrativeExpense"),
        "rd":               _annual(g, "ResearchAndDevelopmentExpense"),
        "amortization":     _annual(g, "AmortizationOfIntangibleAssets",
                                       "AmortizationOfAcquiredIntangibleAssets"),
        "restructuring":    _annual(g, "RestructuringCharges",
                                       "RestructuringAndRelatedCostIncurredCost",
                                       "RestructuringCostsAndAssetImpairmentCharges",
                                       "BusinessExitCosts1"),
        "goodwill_impairment": _annual(g, "GoodwillImpairmentLoss"),
        "asset_impairment":    _annual(g, "AssetImpairmentCharges",
                                          "ImpairmentOfIntangibleAssetsFinitelived",
                                          "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill"),
        "other_opex":          _annual(g, "OtherOperatingIncomeExpenseNet",
                                          "OtherOperatingExpenses"),
        "operating_income": _annual(g, "OperatingIncomeLoss"),
        "interest_exp":     _annual(g, "InterestExpense"),
        "interest_inc":     _annual(g, "InvestmentIncomeInterest",
                                       "InterestAndDividendIncomeOperating",
                                       "InterestIncomeExpenseNet"),
        "pretax_income":    _annual(g,
                                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
        "tax":              _annual(g, "IncomeTaxExpenseBenefit"),
        "net_income":       _annual(g, "NetIncomeLoss", "ProfitLoss"),
        "eps_diluted":      _annual(g, "EarningsPerShareDiluted",
                                       unit="USD/shares", divisor=1),
        "eps_basic":        _annual(g, "EarningsPerShareBasic",
                                       unit="USD/shares", divisor=1),
        "shares_diluted":   _annual(g, "WeightedAverageNumberOfDilutedSharesOutstanding",
                                       unit="shares", divisor=1e6),
        "shares_basic":     _annual(g, "WeightedAverageNumberOfSharesOutstandingBasic",
                                       unit="shares", divisor=1e6),
        "dna":              _annual(g, "DepreciationDepletionAndAmortization",
                                       "DepreciationAndAmortization"),
    }

    result = {
        "fetched": str(date.today()),
        "ticker":  ticker.upper(),
        "company": name,
        "series":  series,
    }
    _cache_path(ticker).write_text(json.dumps(result, indent=2))
    return result


def load_data(ticker: str, cik: str) -> dict:
    """Return cached data if fetched today, otherwise fetch fresh from SEC."""
    cache = _cache_path(ticker)
    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached.get("fetched") == str(date.today()):
            return cached
    return fetch_and_cache(ticker, cik)
