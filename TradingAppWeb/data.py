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


def _annual_instant(facts: dict, *concepts, unit: str = "USD", divisor: float = 1e6) -> dict:
    """
    Merge 10-K instant (balance sheet) data across all concepts.
    Instant facts have no fp/start; we key by the fiscal year-end date year.
    First concept listed takes priority (list the most authoritative concept first).
    """
    annual: dict[str, tuple] = {}
    for concept in reversed(concepts):
        entries = facts.get(concept, {}).get("units", {}).get(unit, [])
        for e in entries:
            if e.get("form") in ("10-K", "10-K/A"):
                yr = e["end"][:4]
                if yr not in annual or e["filed"] > annual[yr][1]:
                    annual[yr] = (e["val"], e["filed"])
    return {yr: v[0] / divisor for yr, v in sorted(annual.items())} if annual else {}


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

        # ── Balance Sheet ──────────────────────────────────────────────────────
        # Current Assets
        "bs_cash":                   _annual_instant(g, "CashAndCashEquivalentsAtCarryingValue", "Cash"),
        "bs_st_investments":         _annual_instant(g, "ShortTermInvestments",
                                                        "AvailableForSaleSecuritiesCurrent",
                                                        "MarketableSecuritiesCurrent"),
        "bs_total_cash_st_inv":      _annual_instant(g, "CashCashEquivalentsAndShortTermInvestments"),
        "bs_accounts_receivable":    _annual_instant(g, "AccountsReceivableNetCurrent"),
        "bs_total_receivables":      _annual_instant(g, "ReceivablesNetCurrent",
                                                        "AccountsReceivableNetCurrent"),
        "bs_inventory":              _annual_instant(g, "InventoryNet"),
        "bs_prepaid_expenses":       _annual_instant(g, "PrepaidExpenseAndOtherAssetsCurrent",
                                                        "PrepaidExpenseCurrent"),
        "bs_deferred_tax_curr":      _annual_instant(g, "DeferredTaxAssetsNetCurrent"),
        "bs_other_current_assets":   _annual_instant(g, "OtherAssetsCurrent"),
        "bs_total_current_assets":   _annual_instant(g, "AssetsCurrent"),
        # Non-Current Assets
        "bs_gross_ppe":              _annual_instant(g, "PropertyPlantAndEquipmentGross"),
        "bs_accum_depreciation":     _annual_instant(g, "AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment"),
        "bs_net_ppe":                _annual_instant(g, "PropertyPlantAndEquipmentNet"),
        "bs_lt_investments":         _annual_instant(g, "LongTermInvestments",
                                                        "AvailableForSaleSecuritiesNoncurrent"),
        "bs_goodwill":               _annual_instant(g, "Goodwill"),
        "bs_other_intangibles":      _annual_instant(g, "IntangibleAssetsNetExcludingGoodwill",
                                                        "FiniteLivedIntangibleAssetsNet"),
        "bs_deferred_tax_lt":        _annual_instant(g, "DeferredIncomeTaxAssetsNet",
                                                        "DeferredTaxAssetsNetNoncurrent"),
        "bs_deferred_charges_lt":    _annual_instant(g, "DeferredCostsNoncurrent"),
        "bs_other_lt_assets":        _annual_instant(g, "OtherAssetsNoncurrent"),
        "bs_total_assets":           _annual_instant(g, "Assets"),
        # Current Liabilities
        "bs_accounts_payable":       _annual_instant(g, "AccountsPayableCurrent"),
        "bs_accrued_expenses":       _annual_instant(g, "AccruedLiabilitiesCurrent",
                                                        "EmployeeRelatedLiabilitiesCurrent"),
        "bs_st_borrowings":          _annual_instant(g, "ShortTermBorrowings", "CommercialPaper"),
        "bs_current_ltd":            _annual_instant(g, "LongTermDebtCurrent"),
        "bs_current_capital_lease":  _annual_instant(g, "FinanceLeaseLiabilityCurrent",
                                                        "CapitalLeaseObligationsCurrent"),
        "bs_income_taxes_payable":   _annual_instant(g, "AccruedIncomeTaxesCurrent",
                                                        "TaxesPayableCurrent"),
        "bs_deferred_tax_liab_curr": _annual_instant(g, "DeferredTaxLiabilitiesCurrent"),
        "bs_other_current_liab":     _annual_instant(g, "OtherLiabilitiesCurrent"),
        "bs_total_current_liab":     _annual_instant(g, "LiabilitiesCurrent"),
        # Non-Current Liabilities
        "bs_lt_debt":                _annual_instant(g, "LongTermDebtNoncurrent"),
        "bs_capital_leases_lt":      _annual_instant(g, "FinanceLeaseLiabilityNoncurrent",
                                                        "CapitalLeaseObligationsNoncurrent"),
        "bs_pension":                _annual_instant(g, "PensionAndOtherPostretirementDefinedBenefitPlansLiabilitiesNoncurrent",
                                                        "DefinedBenefitPensionPlanLiabilitiesNoncurrent"),
        "bs_deferred_tax_liab_nc":   _annual_instant(g, "DeferredIncomeTaxLiabilitiesNet",
                                                        "DeferredTaxLiabilitiesNoncurrent"),
        "bs_other_nc_liab":          _annual_instant(g, "OtherLiabilitiesNoncurrent"),
        "bs_total_liabilities":      _annual_instant(g, "Liabilities"),
        # Equity
        "bs_common_stock":           _annual_instant(g, "CommonStockValue"),
        "bs_apic":                   _annual_instant(g, "AdditionalPaidInCapital",
                                                        "AdditionalPaidInCapitalCommonStock"),
        "bs_retained_earnings":      _annual_instant(g, "RetainedEarningsAccumulatedDeficit"),
        "bs_aoci":                   _annual_instant(g, "AccumulatedOtherComprehensiveIncomeLossNetOfTax"),
        "bs_total_common_equity":    _annual_instant(g, "StockholdersEquity"),
        "bs_minority_interest":      _annual_instant(g, "MinorityInterest",
                                                        "RedeemableNoncontrollingInterestEquityCarryingAmount"),
        "bs_total_equity":           _annual_instant(g, "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        "bs_total_liab_and_equity":  _annual_instant(g, "LiabilitiesAndStockholdersEquity"),
        # Supplementary
        "bs_shares_outstanding":     _annual_instant(g, "CommonStockSharesOutstanding",
                                                        unit="shares", divisor=1e6),
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
