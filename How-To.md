# How-To – TradingApp

Manual processes and step-by-step guides for maintaining the app.

---

## Adding new companies to the list

Companies are defined in `TradingAppWeb/companies.json`. Each entry requires three fields: the stock **ticker**, the **display name**, and the company's **CIK** — a unique identifier assigned by the SEC to every public company that files in the US.

### Step 1 — Find the company's CIK on SEC EDGAR

1. Go to **https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany**
2. Type the company name or ticker in the search box and hit **Search**.
3. In the results, click on the company name that matches.
4. Look at the URL of the resulting page — the CIK is the 10-digit number shown there, e.g.:
   ```
   https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000001800&...
   ```
   The CIK in this example is **0000001800**.
5. Confirm you have the right entity by checking that it shows **10-K** filings in its filing history. If the company is foreign-listed but SEC-registered, it may file **20-F** instead — those are not yet supported.

> **Tip:** If a company has reincorporated (e.g. Medtronic moving to Ireland), search for the new legal entity name, not the original one. The old and new entities have different CIKs and only the current one will have recent filings.

---

### Step 2 — Add the entry to `companies.json`

Open `TradingAppWeb/companies.json`. The file is a JSON array where each object has this structure:

```json
{
  "ticker": "TICKER",
  "name": "Full Company Name",
  "cik": "0000000000"
}
```

Add a new object to the array following the same format. Example — adding Johnson & Johnson:

```json
[
  {
    "ticker": "ABT",
    "name": "Abbott Laboratories",
    "cik": "0000001800"
  },
  {
    "ticker": "MDT",
    "name": "Medtronic plc",
    "cik": "0001613103"
  },
  {
    "ticker": "BSX",
    "name": "Boston Scientific Corporation",
    "cik": "0000885725"
  },
  {
    "ticker": "JNJ",
    "name": "Johnson & Johnson",
    "cik": "0000200406"
  }
]
```

Rules to follow:
- The **ticker** must be uppercase and match the official stock ticker exactly.
- The **CIK** must be zero-padded to 10 digits (e.g. `0000001800`, not `1800`).
- The JSON must remain valid — make sure every object except the last one has a trailing comma.

---

### Step 3 — Launch the app and verify

1. Start the app as usual by double-clicking **`Iniciar App.bat`**.
2. The new company will appear as a chip in the search bar at the top of the page.
3. Click on its chip — the app will fetch its income statement data from SEC EDGAR on first load (this may take a few seconds).
4. Once loaded, data is cached locally in `TradingAppWeb/cache_TICKER.json` and will not be re-fetched until the next day.

If the table loads but some rows are empty, it means that company uses a non-standard XBRL concept name for that metric. This is uncommon but can happen with foreign-registered companies or after major restatements. In that case, contact the development team.
