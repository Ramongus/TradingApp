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


# ── Earnings-release supplement (6-K / HTML) ──────────────────────────────────

def _parse_val(text: str):
    """Parse a financial value string: '492.5' → 492.5, '(141.1)' → -141.1, '—' → None."""
    t = text.strip().replace("\xa0", "").replace(",", "").replace(" ", "").replace("\u2014", "")
    if not t or t in ("—", "–", "-"):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        return float(t) * (-1 if neg else 1)
    except ValueError:
        return None


def _non_empty_tds(tr):
    """Return <td> elements that have actual content (skip spacer cells)."""
    from bs4 import Tag
    result = []
    for td in tr.find_all("td"):
        if td.get_text().replace("\xa0", "").strip():
            result.append(td)
    return result


def _find_annual_6k_url(cik: str, ticker: str, fiscal_year: int):
    """
    Find the primary document URL for the annual earnings release 6-K.
    Looks for 6-K filings in Jan–May of (fiscal_year + 1), preferring filings
    whose primary document filename starts with the company ticker (company-specific
    releases, as opposed to third-party filing-agent documents).
    Returns (url, fiscal_year_str) or (None, None).
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if not r.ok:
        return None, None

    recent   = r.json().get("filings", {}).get("recent", {})
    forms    = recent.get("form", [])
    dates    = recent.get("filingDate", [])
    accs     = recent.get("accessionNumber", [])
    docs     = recent.get("primaryDocument", [])
    cik_int  = str(int(cik))
    target_y = fiscal_year + 1

    candidates = []
    for form, d, acc, doc in zip(forms, dates, accs, docs):
        if form != "6-K":
            continue
        yr, mo = int(d[:4]), int(d[5:7])
        if yr == target_y and 1 <= mo <= 5:
            is_company_doc = doc.lower().startswith(ticker.lower())
            candidates.append((d, acc, doc, is_company_doc))

    if not candidates:
        return None, None

    # Prefer company-specific doc over filing-agent docs; then most recent date
    candidates.sort(key=lambda x: (x[3], x[0]), reverse=True)
    _, acc, doc, _ = candidates[0]
    acc_clean = acc.replace("-", "")
    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc}"
    return doc_url, str(fiscal_year)


def _parse_earnings_release(html: str, fiscal_year: int) -> dict:
    """
    Parse a GPRK-style annual earnings release HTML document.
    Extracts key financial metrics (in millions USD) for the given fiscal_year.
    Returns a dict mapping series keys to float values.

    Table column conventions (after stripping spacer <td>s):
      Income Statement / Cash Flow: label | 4Qcurr | 4Qprev | FYcurr | FYprev
        → FY current at index 3
      Balance Sheet:                label | Dec_curr | Dec_prev
        → current year-end at index 1
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    result = {}

    # ── Income Statement ────────────────────────────────────────────
    IS_MAP = {
        "TOTAL REVENUE":               "revenues",
        "OPERATING PROFIT":            "operating_income",
        "PROFIT BEFORE INCOME TAX":    "pretax_income",
        "Income tax":                  "tax",
        "PROFIT FOR THE PERIOD":       "net_income",
        "Depreciation":                "dna",
        "Impairment":                  "asset_impairment",
    }

    is_table = None
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        if "TOTAL REVENUE" in txt and "PROFIT FOR THE PERIOD" in txt:
            is_table = tbl
            break

    if is_table:
        for tr in is_table.find_all("tr"):
            tds = _non_empty_tds(tr)
            if len(tds) < 4:
                continue
            label = " ".join(tds[0].get_text().replace("\xa0", "").split())
            for known, key in IS_MAP.items():
                if known in label:
                    val = _parse_val(tds[3].get_text())   # FY current
                    if val is not None:
                        result[key] = val
                    break

    # ── Balance Sheet ───────────────────────────────────────────────
    BS_MAP = {
        "Cash at bank and in hand":     "bs_cash",
        "Trade receivables":            "bs_accounts_receivable",
        "Inventories":                  "bs_inventory",
        "Other current assets":         "bs_other_current_assets",
        "Total Current Assets":         "bs_total_current_assets",
        "Property, plant and equipment": "bs_net_ppe",
        "Total Assets":                 "bs_total_assets",
        "Total Equity":                 "bs_total_equity",
        "Total Current Liabilities":    "bs_total_current_liab",
        "Total Liabilities":            "bs_total_liabilities",
        "Total Liabilities and Equity": "bs_total_liab_and_equity",
    }

    bs_table = None
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        if "Total Assets" in txt and "Total Equity" in txt and "Total Current Assets" in txt:
            bs_table = tbl
            break

    lt_debt_done = False
    if bs_table:
        for tr in bs_table.find_all("tr"):
            tds = _non_empty_tds(tr)
            if len(tds) < 2:
                continue
            label = " ".join(tds[0].get_text().replace("\xa0", "").split())
            matched = False
            for known, key in BS_MAP.items():
                if known in label:
                    val = _parse_val(tds[1].get_text())   # current year-end
                    if val is not None:
                        result[key] = val
                    matched = True
                    break
            if not matched and "Borrowings" in label:
                val = _parse_val(tds[1].get_text())
                if val is not None:
                    if not lt_debt_done:
                        result["bs_lt_debt"] = val
                        lt_debt_done = True
                    else:
                        result["bs_st_borrowings"] = val

    # ── Cash Flow ───────────────────────────────────────────────────
    CF_MAP = {
        "Cash flow from operating activities":            "cf_cash_from_ops",
        "Cash flow used in investing activities":         "cf_cash_from_investing",
        "Cash flow (used in) from financing activities":  "cf_cash_from_financing",
    }

    cf_table = None
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        if "Cash flow from operating activities" in txt and "Cash flow used in investing" in txt:
            cf_table = tbl
            break

    if cf_table:
        for tr in cf_table.find_all("tr"):
            tds = _non_empty_tds(tr)
            if len(tds) < 4:
                continue
            label = " ".join(tds[0].get_text().replace("\xa0", "").split())
            for known, key in CF_MAP.items():
                if known in label:
                    val = _parse_val(tds[3].get_text())   # FY current
                    if val is not None:
                        result[key] = val
                    break

    return result


def _supplement_from_earnings_release(series: dict, cik: str, ticker: str) -> dict:
    """
    For IFRS filers: if the most recent fiscal year in XBRL data is behind the
    most recently completed fiscal year, find and parse the annual earnings release
    6-K to fill the gap.

    Only adds data for years NOT already present in the XBRL-sourced series,
    so when the audited 20-F is eventually filed and fetched, its XBRL data
    automatically takes precedence (it will be present in the series before
    this function would add anything).
    """
    if not series.get("revenues"):
        return series

    latest_year  = max(int(y) for y in series["revenues"])
    current_year = date.today().year

    # Most recent completed fiscal year is at least current_year - 1;
    # if our data already reaches that, nothing to do.
    if latest_year >= current_year - 1:
        return series

    fiscal_year = latest_year + 1
    doc_url, fy_str = _find_annual_6k_url(cik, ticker, fiscal_year)
    if not doc_url:
        return series

    try:
        r = requests.get(doc_url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        extracted = _parse_earnings_release(r.text, fiscal_year)
    except Exception:
        return series

    if not extracted:
        return series

    # Merge only for the missing year
    for key, value in extracted.items():
        if key in series and fy_str not in series[key]:
            series[key][fy_str] = value

    return series


# ── SEC EDGAR XBRL ────────────────────────────────────────────────────────────

def _fetch_raw(cik: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _annual_instant(facts: dict, *concepts, unit: str = "USD", divisor: float = 1e6,
                    forms: tuple = ("10-K", "10-K/A")) -> dict:
    """
    Merge annual instant (balance sheet) data across all concepts.
    Instant facts have no fp/start; we key by the fiscal year-end date year.
    First concept listed takes priority (list the most authoritative concept first).
    """
    annual: dict[str, tuple] = {}
    for concept in reversed(concepts):
        entries = facts.get(concept, {}).get("units", {}).get(unit, [])
        for e in entries:
            if e.get("form") in forms:
                yr = e["end"][:4]
                if yr not in annual or e["filed"] > annual[yr][1]:
                    annual[yr] = (e["val"], e["filed"])
    return {yr: v[0] / divisor for yr, v in sorted(annual.items())} if annual else {}


def _annual(facts: dict, *concepts, unit: str = "USD", divisor: float = 1e6,
            forms: tuple = ("10-K", "10-K/A")) -> dict:
    """
    Merge annual FY data across all concepts. For overlapping years the FIRST
    concept listed takes priority (list the most authoritative concept first).
    Values are divided by `divisor` (default: millions).
    """
    annual: dict[str, tuple] = {}
    # Process in reverse so that the first concept overwrites later ones
    for concept in reversed(concepts):
        entries = facts.get(concept, {}).get("units", {}).get(unit, [])
        for e in entries:
            if e.get("form") in forms and e.get("fp") == "FY":
                yr = e["end"][:4]
                if yr not in annual or e["filed"] > annual[yr][1]:
                    annual[yr] = (e["val"], e["filed"])
    return {yr: v[0] / divisor for yr, v in sorted(annual.items())} if annual else {}


def _build_series_ifrs(i: dict) -> dict:
    """Build the series dict for IFRS reporters (20-F filers)."""
    f  = ("20-F", "20-F/A")
    a  = lambda *c, **kw: _annual(i, *c, forms=f, **kw)
    ai = lambda *c, **kw: _annual_instant(i, *c, forms=f, **kw)
    return {
        "revenues":            a("Revenue"),
        "cogs":                a("OperatingExpense", "RawMaterialsAndConsumablesUsed"),
        "sga":                 a("AdministrativeExpense", "SalesAndMarketingExpense"),
        "rd":                  {},
        "amortization":        a("AdjustmentsForAmortisationExpense"),
        "restructuring":       {},
        "goodwill_impairment": {},
        "asset_impairment":    a("ImpairmentLossRecognisedInProfitOrLoss", "ImpairmentLoss"),
        "other_opex":          a("MiscellaneousOtherOperatingExpense", "OtherExpenseByNature"),
        "operating_income":    a("ProfitLossFromOperatingActivities"),
        "interest_exp":        a("FinanceCosts"),
        "interest_inc":        a("FinanceIncome"),
        "pretax_income":       a("ProfitLossBeforeTax"),
        "tax":                 a("IncomeTaxExpenseContinuingOperations"),
        "net_income":          a("ProfitLoss"),
        "eps_diluted":         a("DilutedEarningsLossPerShare",  unit="USD/shares", divisor=1),
        "eps_basic":           a("BasicEarningsLossPerShare",    unit="USD/shares", divisor=1),
        "shares_diluted":      a("AdjustedWeightedAverageShares", unit="shares", divisor=1e6),
        "shares_basic":        a("WeightedAverageShares",         unit="shares", divisor=1e6),
        "dna":                 a("DepreciationExpense", "AdjustmentsForDepreciationExpense"),
        # Balance Sheet — Current Assets
        "bs_cash":                   ai("CashAndCashEquivalents"),
        "bs_st_investments":         ai("OtherCurrentFinancialAssets"),
        "bs_total_cash_st_inv":      {},
        "bs_accounts_receivable":    ai("TradeReceivables", "TradeAndOtherReceivables"),
        "bs_total_receivables":      ai("TradeAndOtherReceivables", "TradeReceivables"),
        "bs_inventory":              ai("Inventories"),
        "bs_prepaid_expenses":       ai("CurrentPrepaymentsAndOtherCurrentAssets"),
        "bs_deferred_tax_curr":      {},
        "bs_other_current_assets":   ai("CurrentPrepaymentsAndOtherCurrentAssets"),
        "bs_total_current_assets":   ai("CurrentAssets"),
        # Balance Sheet — Non-Current Assets
        "bs_gross_ppe":              {},
        "bs_accum_depreciation":     {},
        "bs_net_ppe":                ai("PropertyPlantAndEquipment"),
        "bs_lt_investments":         {},
        "bs_goodwill":               {},
        "bs_other_intangibles":      {},
        "bs_deferred_tax_lt":        ai("DeferredTaxAssets"),
        "bs_deferred_charges_lt":    {},
        "bs_other_lt_assets":        ai("NoncurrentPrepaymentsAndNoncurrentAccruedIncome",
                                        "OtherNoncurrentFinancialAssets"),
        "bs_total_assets":           ai("Assets"),
        # Balance Sheet — Current Liabilities
        "bs_accounts_payable":       ai("TradeAndOtherCurrentPayables", "TradeAndOtherPayables"),
        "bs_accrued_expenses":       {},
        "bs_st_borrowings":          ai("ShorttermBorrowings"),
        "bs_current_ltd":            {},
        "bs_current_capital_lease":  {},
        "bs_income_taxes_payable":   ai("CurrentTaxLiabilities"),
        "bs_deferred_tax_liab_curr": {},
        "bs_other_current_liab":     {},
        "bs_total_current_liab":     ai("CurrentLiabilities"),
        # Balance Sheet — Non-Current Liabilities
        "bs_lt_debt":                ai("LongtermBorrowings", "Borrowings"),
        "bs_capital_leases_lt":      {},
        "bs_pension":                {},
        "bs_deferred_tax_liab_nc":   ai("DeferredTaxLiabilities"),
        "bs_other_nc_liab":          {},
        "bs_total_liabilities":      ai("Liabilities"),
        # Balance Sheet — Equity
        "bs_common_stock":           ai("IssuedCapital"),
        "bs_apic":                   ai("SharePremium"),
        "bs_retained_earnings":      ai("RetainedEarnings"),
        "bs_aoci":                   ai("OtherReserves", "ReserveOfExchangeDifferencesOnTranslation"),
        "bs_total_common_equity":    ai("EquityAttributableToOwnersOfParent"),
        "bs_minority_interest":      ai("NoncontrollingInterests"),
        "bs_total_equity":           ai("Equity"),
        "bs_total_liab_and_equity":  ai("EquityAndLiabilities"),
        "bs_shares_outstanding":     ai("NumberOfSharesOutstanding", unit="shares", divisor=1e6),
        # Cash Flow — Operating
        "cf_depreciation":           a("AdjustmentsForDepreciationExpense", "DepreciationExpense"),
        "cf_amort_deferred":         a("AdjustmentsForAmortisationExpense"),
        "cf_minority_interest_cf":   {},
        "cf_gain_loss_asset":        {},
        "cf_asset_writedown":        a("ImpairmentLossRecognisedInProfitOrLoss"),
        "cf_stock_comp":             a("AdjustmentsForSharebasedPayments"),
        "cf_tax_benefit_stock":      {},
        "cf_bad_debt_provision":     {},
        "cf_discontinued_ops_cf":    {},
        "cf_other_operating":        a("AdjustmentsForDecreaseIncreaseInOtherAssets",
                                       "AdjustmentsForIncreaseDecreaseInOtherLiabilities"),
        "cf_change_ar":              a("AdjustmentsForDecreaseIncreaseInTradeAccountReceivable"),
        "cf_change_inventory":       a("AdjustmentsForDecreaseIncreaseInInventories"),
        "cf_change_ap":              a("AdjustmentsForIncreaseDecreaseInTradeAccountPayable"),
        "cf_change_income_taxes":    {},
        "cf_change_other_assets":    a("AdjustmentsForDecreaseIncreaseInOtherAssets"),
        "cf_cash_from_ops":          a("CashFlowsFromUsedInOperatingActivities"),
        # Cash Flow — Investing
        "cf_capex":                  a("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
        "cf_sale_ppe":               a("ProceedsFromOtherLongtermAssetsClassifiedAsInvestingActivities"),
        "cf_acquisitions":           a("CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities"),
        "cf_divestitures":           {},
        "cf_inv_securities":         {},
        "cf_other_investing":        {},
        "cf_cash_from_investing":    a("CashFlowsFromUsedInInvestingActivities"),
        # Cash Flow — Financing
        "cf_debt_issued":            a("ProceedsFromBorrowingsClassifiedAsFinancingActivities"),
        "cf_debt_repaid":            a("RepaymentsOfBorrowingsClassifiedAsFinancingActivities"),
        "cf_stock_issued":           a("IssueOfEquity"),
        "cf_stock_repurchased":      a("PaymentsToAcquireOrRedeemEntitysShares"),
        "cf_dividends_common":       a("DividendsPaidClassifiedAsFinancingActivities"),
        "cf_dividends_total":        a("DividendsPaidClassifiedAsFinancingActivities"),
        "cf_other_financing":        {},
        "cf_cash_from_financing":    a("CashFlowsFromUsedInFinancingActivities"),
        # Cash Flow — Other
        "cf_fx_effect":              a("EffectOfExchangeRateChangesOnCashAndCashEquivalents"),
        "cf_net_change_cash":        a("IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges"),
        "cf_interest_paid":          {},
        "cf_taxes_paid":             {},
    }


def fetch_and_cache(ticker: str, cik: str) -> dict:
    """Force a fresh fetch from SEC EDGAR, overwrite cache, return result."""
    raw  = _fetch_raw(cik)
    g    = raw["facts"].get("us-gaap", {})
    name = raw.get("entityName", ticker)

    # Detect IFRS reporters (e.g. foreign private issuers filing 20-F)
    i = raw["facts"].get("ifrs-full", {})
    if len(i) > len(g):
        series = _build_series_ifrs(i)
        series = _supplement_from_earnings_release(series, cik, ticker)
        result = {
            "fetched": str(date.today()),
            "ticker":  ticker.upper(),
            "company": name,
            "series":  series,
        }
        _cache_path(ticker).write_text(json.dumps(result, indent=2))
        return result

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

        # ── Cash Flow Statement ────────────────────────────────────────────────
        # Operating — non-cash adjustments
        "cf_depreciation":           _annual(g, "Depreciation", "DepreciationNonproduction"),
        "cf_amort_deferred":         _annual(g, "AmortizationOfFinancingCostsAndDiscounts",
                                                "AmortizationOfFinancingCosts"),
        "cf_minority_interest_cf":   _annual(g, "MinorityInterestInNetIncomeLossMinorityInterestNotIncludingDiscontinuedOperations",
                                                "NetIncomeLossAttributableToNoncontrollingInterest"),
        "cf_gain_loss_asset":        _annual(g, "GainLossOnSaleOfPropertyPlantEquipment",
                                                "GainLossOnDispositionOfAssets1",
                                                "GainLossOnSaleOfBusiness"),
        "cf_asset_writedown":        _annual(g, "AssetImpairmentCharges",
                                                "RestructuringCostsAndAssetImpairmentCharges"),
        "cf_stock_comp":             _annual(g, "ShareBasedCompensation",
                                                "AllocatedShareBasedCompensationExpense"),
        "cf_tax_benefit_stock":      _annual(g, "ExcessTaxBenefitFromShareBasedCompensationOperatingActivities"),
        "cf_bad_debt_provision":     _annual(g, "ProvisionForDoubtfulAccounts",
                                                "ProvisionForLoanLeaseAndOtherLosses"),
        "cf_discontinued_ops_cf":    _annual(g, "CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations"),
        "cf_other_operating":        _annual(g, "OtherOperatingActivitiesCashFlowStatement",
                                                "IncreaseDecreaseInOtherOperatingLiabilities"),
        # Operating — working capital changes
        "cf_change_ar":              _annual(g, "IncreaseDecreaseInAccountsReceivable"),
        "cf_change_inventory":       _annual(g, "IncreaseDecreaseInInventories"),
        "cf_change_ap":              _annual(g, "IncreaseDecreaseInAccountsPayable"),
        "cf_change_income_taxes":    _annual(g, "IncreaseDecreaseInAccruedIncomeTaxesPayable",
                                                "IncreaseDecreaseInIncomeTaxesPayable"),
        "cf_change_other_assets":    _annual(g, "IncreaseDecreaseInOtherOperatingCapitalNet"),
        # Operating — total
        "cf_cash_from_ops":          _annual(g, "NetCashProvidedByUsedInOperatingActivities"),
        # Investing
        "cf_capex":                  _annual(g, "PaymentsToAcquirePropertyPlantAndEquipment"),
        "cf_sale_ppe":               _annual(g, "ProceedsFromSaleOfPropertyPlantAndEquipment"),
        "cf_acquisitions":           _annual(g, "PaymentsToAcquireBusinessesNetOfCashAcquired",
                                                "PaymentsToAcquireBusinessesGross"),
        "cf_divestitures":           _annual(g, "ProceedsFromDivestitureOfBusinessesNetOfCashDivested",
                                                "ProceedsFromDivestitureOfBusiness"),
        "cf_inv_securities":         _annual(g, "PaymentsToAcquireInvestments",
                                                "PaymentsToAcquireMarketableSecurities",
                                                "PaymentsToAcquireAvailableForSaleSecurities"),
        "cf_other_investing":        _annual(g, "PaymentsForProceedsFromOtherInvestingActivities",
                                                "OtherPaymentsToAcquireBusinesses"),
        "cf_cash_from_investing":    _annual(g, "NetCashProvidedByUsedInInvestingActivities"),
        # Financing
        "cf_debt_issued":            _annual(g, "ProceedsFromIssuanceOfLongTermDebt",
                                                "ProceedsFromDebt",
                                                "ProceedsFromIssuanceOfDebt"),
        "cf_debt_repaid":            _annual(g, "RepaymentsOfLongTermDebt",
                                                "RepaymentsOfDebt"),
        "cf_stock_issued":           _annual(g, "ProceedsFromIssuanceOfCommonStock"),
        "cf_stock_repurchased":      _annual(g, "PaymentsForRepurchaseOfCommonStock"),
        "cf_dividends_common":       _annual(g, "PaymentsOfDividendsCommonStock"),
        "cf_dividends_total":        _annual(g, "PaymentsOfDividends",
                                                "PaymentsOfDividendsCommonStock"),
        "cf_other_financing":        _annual(g, "ProceedsFromPaymentsForOtherFinancingActivities",
                                                "PaymentsForOtherFinancingActivities"),
        "cf_cash_from_financing":    _annual(g, "NetCashProvidedByUsedInFinancingActivities"),
        # Other
        "cf_fx_effect":              _annual(g, "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                                                "EffectOfExchangeRateOnCashAndCashEquivalents"),
        "cf_net_change_cash":        _annual(g, "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
                                                "CashAndCashEquivalentsPeriodIncreaseDecrease"),
        # Supplementary
        "cf_interest_paid":          _annual(g, "InterestPaidNet", "InterestPaid"),
        "cf_taxes_paid":             _annual(g, "IncomeTaxesPaid", "IncomeTaxesPaidNet"),
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
