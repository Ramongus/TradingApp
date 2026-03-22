# Changelog – TradingApp

---

### [2026-03-20] Revisión de campos calculados — Cash Flow per Share y resumen

> si [Cash Flow per Share = Cash from Operations / Diluted Shares Outstanding]

- `app.py`: Agregado `cf_per_share` en `compute_derived()` — `cf_cash_from_ops / shares_diluted` (ambos en millones, resultado en USD/share).
- `app.py`: Reemplazado `empty()` de "Cash Flow per Share" en `build_cf_table()` por `R("...", "cf_per_share", "normal", "eps")`. Calculado en `_local` dentro de la función.
- `app.py`: Actualizada entrada en `_CF_COMP_METRICS`: `__empty__` → `cf_per_share` con `kind="eps"`.
- Todos los campos calculados revisados y confirmados: Gross Profit, Total OpEx, EBITDA, Effective Tax Rate, YoY %, márgenes, D&A Others, FCF, FCF YoY/Margins, Cash End/Begin of Period, Cash Flow per Share.

---

### [2026-03-20] Revisión de campos calculados — Cash Beginning of Period

> si [cash beginning of period = bs_cash del año anterior]

- `app.py`: Agregado helper `_prior_year_series(series, display_years)` — dado una serie y una lista de años a mostrar, devuelve una nueva serie donde cada año tiene el valor del año anterior.
- `app.py`: Agregado `cash_begin` en `compute_derived()` usando `_prior_year_series(bs_cash, display_years)`.
- `app.py`: Reemplazado `empty()` de "Cash Beginning of Period" en `build_cf_table()` por `R("...", "cash_begin")`. La función usa `_prior_year_series` internamente vía `_local`.
- `app.py`: Actualizada entrada en `_CF_COMP_METRICS`: `__empty__` → `cash_begin`.

---

### [2026-03-20] Revisión de campos calculados — Free Cash Flow

> Si, usemos esa formula [Cash from Operations − CapEx]

- `app.py`: Agregado `fcf` en `compute_derived()` — calculado como `cf_cash_from_ops − cf_capex` (CapEx viene positivo de XBRL).
- `app.py`: Reemplazados los `empty()` de Free Cash Flow en `build_cf_table()` por filas reales: valor, % YoY y % Margins. `fcf` se calcula localmente dentro de la función (igual que `dna_other`) dado que trabaja con series raw.
- `app.py`: Actualizadas las 3 entradas de FCF en `_CF_COMP_METRICS` reemplazando `__empty__` por `fcf` con sus respectivos `kind` (`num`, `yoy`, `margin:fcf/revenues`).

---

### [2026-03-20] Revisión de campos calculados — D&A Others

> Prefiero dejarlo como viene directo, pero si hay nuevas filas para agregar con informacion directa de XBRL me gustaría agregarlas. En caso de que no las haya me gustaria al menos que el total (dna) sea cf_depreciation + amortization + OTHERS (calculated by us to see the difference in case of need it)

- `app.py`: Agregado `dna_other` en `compute_derived()` — calculado como `dna − cf_depreciation − amortization`. Solo aparece en años donde el resultado es distinto de cero (diferencia real entre el total XBRL y la suma de sus componentes).
- `app.py`: Agregada fila "Others D&A" en `build_cf_table()` entre "Amortization of Intangibles" y "Total D&A". La función calcula `dna_other` internamente dado que trabaja con series raw.
- `app.py`: Agregada fila "Others D&A" en `_CF_COMP_METRICS` para que aparezca también en la vista de comparación.

---

### [2026-03-20] Corregir orden de secciones en la vista de comparación

> Cuando visualizo una empresa veo: Income Statement, Cash Flow, Balance. Pero al usar la herramienta de comparación el orden entre cash flow y balance esta invertido.

- `app.py`: Corregido el orden en `build_comparison_table()`: `_COMP_METRICS + _CF_COMP_METRICS + _BS_COMP_METRICS` (antes estaba `_BS_COMP_METRICS + _CF_COMP_METRICS`). Ahora coincide con el orden de la vista individual: Income Statement → Cash Flow → Balance Sheet.

---

### [2026-03-20] Revertir suplemento automático de earnings release

> Si, hay que revertirlo. El flujo tiene que ser Datos del SEC EDGAR, en caso de faltantes, pedir al usuario que brinde archivos de los cuales extraer los datos faltantes.

- `data.py`: Eliminadas las funciones `_parse_val`, `_non_empty_tds`, `_find_annual_6k_url`, `_parse_earnings_release` y `_supplement_from_earnings_release`.
- `data.py`: Eliminada la llamada a `_supplement_from_earnings_release` en `fetch_and_cache()`.
- `CLAUDE.md`: Reemplazadas las 3 reglas sobre datos desactualizados por una sola: buscar siempre datos auditados en SEC EDGAR; si faltan los más recientes, informar al usuario para que provea un archivo `.txt` con los datos de otra fuente.
- Cache de GPRK eliminado para forzar un fetch limpio solo desde XBRL.

---

### [2026-03-20] Suplementar datos faltantes desde earnings release (6-K)

> me parece bien que probemos con yFinance cuando tenemos información desactualizada. [...] Vayamos siempre por la Opcion B en los casos que no podamos obtener los ultimos datos. Sin embargo, asegurate que siempre que esten publicados los datos auditados, reemplazar los datos que extraigas de los html

- `data.py`: Agregado `_parse_val()` — parsea strings financieros con notación de paréntesis para negativos (`(141.1)` → `-141.1`).
- `data.py`: Agregado `_non_empty_tds()` — helper que filtra celdas spacer de las tablas HTML.
- `data.py`: Agregado `_find_annual_6k_url(cik, ticker, fiscal_year)` — consulta la submissions API de SEC EDGAR para encontrar el 6-K de earnings release anual. Busca filings 6-K de enero–mayo del año siguiente al fiscal; prioriza documentos cuyo nombre empieza con el ticker (releases propios de la empresa vs. agentes de filing externos tipo `dp*.htm`).
- `data.py`: Agregado `_parse_earnings_release(html, fiscal_year)` — parsea con BeautifulSoup el HTML del earnings release. Extrae Income Statement (revenues, operating_income, pretax_income, tax, net_income, dna, asset_impairment), Balance Sheet (cash, receivables, inventory, PPE, total assets/liabilities/equity, deuda LT y CT) y Cash Flow (ops, investing, financing). Índice FY actual: columna 3 en IS/CF, columna 1 en BS (después de filtrar spacers).
- `data.py`: Agregado `_supplement_from_earnings_release(series, cik, ticker)` — orquesta la búsqueda y merge. Solo agrega datos para años **ausentes** en la serie XBRL; cuando el 20-F audited es presentado y fetcheado, sus datos XBRL ya estarán presentes y el suplemento no sobreescribe nada.
- `data.py`: Llamada a `_supplement_from_earnings_release` integrada en el branch IFRS de `fetch_and_cache()`.
- Resultado verificado: GPRK ahora muestra FY2025 con Revenue $492.5M, Operating Income $110.5M, Net Income $49.7M, Cash $100.3M, Total Assets $1,040.4M.
- Regla establecida: para emisores IFRS con datos XBRL desactualizados, siempre intentar suplementar desde el earnings release 6-K. Los datos auditados del 20-F reemplazan automáticamente al ser publicados.

---

### [2026-03-20] Verificación de datos recientes en GPRK

> Por alguna razón veo que de la anterior sesion que trabajamos juntos a esta olvidaste seguir ciertas metodologias [...] los datos más recientes que obtuviste son de 2014. La idea es tener la información más real y reciente posible. EN TODOS LOS CASOS. Intenta corregir esto en el caso de GeoPark basandote en como lo habiamos logrado en la sesion anterior.

- Diagnóstico: el caché de GPRK (recreado tras el fix IFRS) ya contiene datos de 2015 → 2024 para todas las series principales. El "2014" reportado correspondía al estado roto previo (búsqueda de conceptos `us-gaap` en un filer IFRS).
- La diferencia entre GPRK (hasta 2024) y ABT/MDT/BSX (hasta 2025) es estructural: los emisores extranjeros tienen 6 meses tras el cierre fiscal para presentar su 20-F; el FY2025 de GPRK no estará disponible en la SEC hasta ~junio 2026.
- No se requirieron cambios de código; el fix IFRS de la entrada anterior resuelve el problema completo.
- Creado `CLAUDE.md` en la raíz del proyecto con metodología, reglas de desarrollo y estructura del proyecto para que persistan entre sesiones.

---

### [2026-03-20] Soporte para empresas IFRS (emisores extranjeros con 20-F)

> Parece que a pesar de ser el CIK correcto, no esta trayendo información. La tabla esta vacia.

- `data.py`: Detectado que GeoPark (y cualquier emisor extranjero) reporta bajo `ifrs-full` en lugar de `us-gaap`. La detección es automática: si `len(ifrs-full) > len(us-gaap)`, se usa el namespace IFRS.
- `data.py`: Agregado parámetro `forms` a `_annual()` y `_annual_instant()` (default `("10-K", "10-K/A")`), permitiendo filtrar por `20-F`/`20-F/A` para emisores extranjeros.
- `data.py`: Creada función `_build_series_ifrs()` con el mapeo completo de conceptos IFRS a los mismos keys que usa el resto de la app — cubre Income Statement, Balance Sheet y Cash Flow Statement.
- `DesignDocuments/How-To.md`: Actualizado para reflejar que empresas con 20-F ahora son soportadas automáticamente.

---

### [2026-03-20] Agregar GeoPark Ltd (GPRK) al listado de empresas

> Podrias agregar Geopark Ltd (GPRK) al listado de empresas?

- `companies.json`: Agregado GeoPark Ltd con ticker `GPRK` y CIK `0001464591` (verificado contra SEC EDGAR — el CIK inicial `0001596530` era incorrecto y correspondía a otra empresa).

---

### [2026-03-20] Agregar Balance Sheet y Cash Flow Statement a la vista de comparación

> Add all Cash Flow Statement and Balance Sheet values to the comparision between compnaies when using the compare tool. From now on, any time some value is added to the main page it should be shown in the compartive too.

- `app.py`: Extended `compute_derived()` to pass through all `bs_*` and `cf_*` raw series into the derived dict, plus computed `bs_accum_depreciation_neg`. Also exposed `amortization` and `dna` directly so CF comp metrics can reference them.
- `app.py`: Added `_BS_COMP_METRICS` list — mirrors every row in `build_balance_sheet_table()`, covering Assets, Liabilities, Equity, and Supplementary sections.
- `app.py`: Added `_CF_COMP_METRICS` list — mirrors every row in `build_cf_table()`, covering Operating, Investing, Financing, and Supplementary sections. Calculated/pending rows use `"__empty__"` key and render as blank.
- `app.py`: Added `"__section__", "Income Statement"` header to `_COMP_METRICS` so all three statements are clearly labeled in the comparison table.
- `app.py`: Updated `build_comparison_table()` to concatenate all three metric lists (`_COMP_METRICS + _BS_COMP_METRICS + _CF_COMP_METRICS`). Updated `_company_values()` to handle `__empty__` keys and use `.get()` for all derived dict lookups (no more KeyErrors on missing keys).
- `compare.html`: Updated subtitle from "Income Statement" to "Income Statement · Cash Flow · Balance Sheet".
- Rule established: any row added to the main single-company view must also be added to the corresponding `_*_COMP_METRICS` list.

---

### [2026-03-20] Agregar tabla de Cash Flow Statement debajo del Balance Sheet

> I have added a CashFlowStatementExample.txt file. Do the same as with the Balance Sheet example. Get all public values you can and create a third table below the balance sheet. Values that has to be calculated we will check them later toguether one by one.

- `data.py`: Added ~30 new `cf_` series to `fetch_and_cache()` using `_annual()` (duration facts, same mechanism as income statement). Covers: Operating adjustments (depreciation, amortization of deferred charges, minority interest, gain/loss on asset sale, asset writedown, stock-based comp, tax benefit from stock options, bad debt provision, discontinued ops, other operating), working capital changes (AR, inventory, AP, income taxes, other), Cash from Operations total; Investing (capex, sale of PP&E, acquisitions, divestitures, securities investments, other, Cash from Investing total); Financing (debt issued, debt repaid, stock issued, stock repurchased, common dividends, total dividends, other, Cash from Financing total); FX effect; Net change in cash; Supplementary (interest paid, taxes paid).
- `app.py`: Added `build_cf_table()` function. Calculated fields left empty pending verification: Memo NWC change, Free Cash Flow, FCF % YoY, FCF % margins, Cash beginning of period, Cash flow per share. Cash end of period reuses `bs_cash`.
- `app.py`: Updated `company_view` route to compute and pass `cf_rows` to template.
- `index.html`: Added Cash Flow Statement table between Income Statement and Balance Sheet, with same column structure, `data-col` attributes, section headers, and row styles.
- `index.html`: Extended row-hiding JS selector to cover `#cfTable` tbody rows.
- Deleted stale company cache files to force fresh fetch with CF fields.

---

### [2026-03-20] Agregar tabla de Balance Sheet debajo del Income Statement

> Movi algunos archivos a una carpeta con nombre DesignDocuments. Ahora vamos a trabajar en agregar debajo de la tabla de Income Statement otra con el Balance Sheet (todo en la misma pagina). Dentro de Design Documents encontraras un archivo 'BalanceSheetExample.txt' para que uses como ejemplo. Llena en la tabla los valores que se encuentren publicos, si ves que falta alguno de los que podes encontrar publicos en el template agregalo. Los valores que correspondan a calculos los iremos verificando luego 1 a 1 juntos.

- `data.py`: Added `_annual_instant()` function for balance sheet instant (point-in-time) XBRL facts — filters by `form` in `10-K`/`10-K/A`, deduplicates by fiscal year taking the most recently filed value.
- `data.py`: Added 40+ balance sheet series to `fetch_and_cache()` using `bs_` prefix — covers Current Assets (cash, ST investments, receivables, inventory, prepaid, deferred tax, other), Non-Current Assets (gross/net PP&E, accumulated depreciation, LT investments, goodwill, intangibles, deferred tax, deferred charges, other LT), Current Liabilities (AP, accrued exp, ST borrowings, current LTD, current capital lease, income taxes payable, deferred tax liab, other), Non-Current Liabilities (LT debt, capital leases, pension, deferred tax liab NC, other NC), Equity (common stock, APIC, retained earnings, AOCI, total common equity, minority interest, total equity, total L&E), and shares outstanding.
- `app.py`: Added `build_balance_sheet_table()` — builds flat list of row dicts using same structure as `build_table()`. Accumulated depreciation is negated for display. Calculated supplementary fields (Book Value/Share, Tangible Book Value, Total Debt, Net Debt) are left empty pending one-by-one verification.
- `app.py`: Updated `company_view` route to compute and pass `bs_rows` to template.
- `index.html`: Added Balance Sheet section below the Income Statement table with a section heading, same column structure (`data-col` attributes), and same row styles (bold for totals, revenue-highlight for Total Assets / Total Liabilities / Total L&E, section headers for Assets / Liabilities / Equity / Supplementary).
- `index.html`: Extended row-hiding JS to cover both `#mainTable` and `#bsTable` tbody rows.
- `index.html`: Updated page title and subtitle from "Income Statement" to "Income Statement & Balance Sheet".
- Deleted stale company cache files so fresh data with BS fields is fetched on next load.

---

### [2026-03-20] Ocultar métricas completas en la vista de comparación

> Cuando comparas empresas, no debería ser capaz de ocultar individualmente cualquier fila. Debería poder ocultar unicamente alguna de las filas que representan algun valor, ejemplo "total revenues" o "Gross profit" pero no las individuales de cada empresa. Y al ocultar la fila que representa un valor, automaticamente ocultar las correspondientes al mismo de todas las empresas que estan siendo comparadas.

- El botón `×` ahora solo se inyecta en filas `comp-metric` (las de encabezado de métrica), no en las filas individuales de empresa
- Al ocultar una métrica, la función `getMetricGroup()` recoge automáticamente todas las filas `comp-data` y `comp-pct` que le siguen hasta la próxima métrica o sección
- El stack de historial almacena grupos de filas (en lugar de filas individuales), por lo que **Undo** y **Reset rows** recuperan el grupo completo de una métrica de golpe

---

### [2026-03-20] Ocultar filas en la vista de comparación

> Agregale la misma funcionalidad que tiene la tabla cuando es de una sola empresa para poder ocultar ciertas filas de la tabla.

- Añadidos estilos `.row-hidden`, `.hide-btn` y `.btn-row-ctrl` a `compare.html`
- Añadidos botones **Undo** y **Reset rows** al topbar de la vista de comparación
- Añadida lógica JavaScript de hide/undo/reset idéntica a la de `index.html`

---

### [2026-03-20] Herramienta de comparación multi-empresa

> Me gustaría tener una herramienta de comparación. Es decir, seleccionar un grupo de empresas (hasta 5 a la vez) y poder ver la diferencia de sus valores en la misma tabla.

- Añadido botón **Compare** en la barra de navegación de `index.html`
  - Al activarlo, los chips de empresa pasan a modo selección (sin navegar)
  - Se pueden seleccionar hasta 5 empresas; el botón "Compare (N)" se activa con 2+
  - Chips no seleccionables se atenúan al llegar al límite de 5
- Refactorizado `app.py`: extraída función `compute_derived()` con toda la lógica de series calculadas, compartida entre vista individual y comparación
- Añadida función `build_comparison_table()` en `app.py`: construye tabla plana con filas `comp-section`, `comp-metric`, `comp-data` y `comp-pct`
- Añadida ruta `/compare?tickers=ABT,MDT,BSX` en `app.py`
- Creado `templates/compare.html`:
  - Tabla con sub-filas por empresa bajo cada métrica
  - Cada empresa identificada con un color único (azul, morado, verde, naranja, rosa)
  - Pastillas con precio y cambio diario por empresa en la leyenda superior
  - Control de años (3–10) igual al de la vista individual
  - Barra de navegación con enlace "Back" y acceso rápido a vista individual de cada empresa
  - Colores positivo/negativo y resaltado de columna más reciente

---

### [2026-03-20] Ocultar filas con Undo y Reset

> Me gustaría de alguna manera poder ocultar filas de la tabla y tener un boton para recuperar la ultima que oculte y otro para recuperar todas y volver a la tabla original.

- Añadido botón `×` en cada fila que aparece al hacer hover sobre la fila; al clickearlo la oculta y la apila en un historial
- Añadido botón **Undo** en el topbar: muestra la última fila ocultada (LIFO)
- Añadido botón **Reset rows** en el topbar: muestra todas las filas ocultadas y limpia el historial
- Ambos botones aparecen deshabilitados cuando no hay filas ocultas
- Implementado 100% client-side con JavaScript, sin recarga de página

---

### [2026-03-20] Control de años a mostrar en la tabla

> Me gustaría poder especificar cuantos años mostrar en la tabla, siempre contando desde el más reciente obviamente y como minimo 3 y maximo 10.

- Añadido control "Years" en el topbar con botones `−` y `+`
- Mínimo 3 años, máximo igual al total de años disponibles para la empresa (hasta 10)
- Siempre muestra los años más recientes; los más antiguos se ocultan al reducir
- Implementado client-side con JavaScript: sin recarga de página, oculta/muestra columnas instantáneamente via `data-col` y clase `col-hidden`
- Los botones `−` y `+` se deshabilitan automáticamente al alcanzar los límites

---

### [2026-03-20] Precio y cambio porcentual diario junto al nombre de la empresa

> Me gustaría agregar a la derecha del nombre de la empresa el ultimo precio de la acción del dia anterior. ademas al lado del precio entre parentesis el cambio porcentual de ese mismo ultimo dia.

- Instalada librería `yfinance`
- Creado `TradingAppWeb/prices.py`: obtiene el último precio de cierre y el cambio porcentual diario via Yahoo Finance
  - Cachea los datos en `cache_prices.json` por ticker y por día (el precio de ayer no cambia)
  - Devuelve `None` gracefully si la llamada falla
- Actualizado `app.py` para llamar a `get_price_info(ticker)` y pasar `price` y `change_pct` al template
- Actualizado `index.html`:
  - Precio y porcentaje aparecen en línea junto al nombre y ticker de la empresa
  - Cambio positivo en verde con fondo verde suave; negativo en rojo con fondo rojo suave
  - El bloque de precio se oculta automáticamente si los datos no están disponibles

---

### [2026-03-20] Celdas vacías para valores cero en gastos opcionales

> Respecto a lo que encontraste en goodwill_impairment hagamos que aunque reporte cero la celda aparezca vacia.

- Añadido helper `neg_nz` en `app.py` que filtra tanto `None` como `0`
- Aplicado a `restructuring`, `goodwill_impairment`, `asset_impairment` y `other_opex`: si la empresa reporta explícitamente cero, la celda aparece vacía en lugar de mostrar "0"
- Los campos core (COGS, SGA, R&D, etc.) mantienen el comportamiento anterior y sí muestran cero si aplica

---

### [2026-03-20] Revisión y corrección de campos calculados

> Podrias verificar cuales de los campos de la tabla de income statement no son datos traidos directamente de la información publica y que revisemos juntos cómo debería calcularse cada uno de estos campos?
> [...]
> Punto 1 - Es correcto dejemoslo asi. Punto 2 - Me gustaría agregar a la tabla TODAS las filas con TODOS los gastos operativos y que el calculo final sea el verdadero total. Si alguna empresa no tiene cierto gasto que simplemente quede vacio en la tabla. Esta es una regla para seguir en todos los campos, siempre traeremos la mayor cantidad de información que podamos de los datos publicos. Es importante que los datos que se muestran en la tabla sean 100% reales y capturados tal cual esten publicados. Punto 3 - De momento dejemoslo asi. Punto 4 - Es correcto, confirmado. Punto 5 - que te parece si hacemos (valor año N) / (valor año N-1) - 1? Punto 6 - es correcto, confirmado. Punto 7 - Si. Dejemos unicamente el campo de Total Revenues.

- Eliminada la fila "Revenues" duplicada; se conserva únicamente "Total Revenues"
- Corregida fórmula YoY: `(N / N-1) − 1` en lugar de `(N − N-1) / |N-1|`
- Añadidos nuevos conceptos XBRL en `data.py` para capturar todos los gastos operativos:
  - `restructuring`: `RestructuringCharges` y variantes
  - `goodwill_impairment`: `GoodwillImpairmentLoss`
  - `asset_impairment`: `AssetImpairmentCharges` y variantes
  - `other_opex`: `OtherOperatingIncomeExpenseNet`
- Añadidas las filas correspondientes en la tabla: Restructuring Charges, Goodwill Impairment, Asset Impairment, Other Operating Income (Expense)
- Recalculado `Total Operating Expenses = −(Gross Profit − Operating Income)` para garantizar que el total siempre cuadre exactamente con los datos públicos, independientemente de qué líneas individuales reporte cada empresa
- Establecida regla general: mostrar siempre la máxima información disponible; si una empresa no reporta un campo, la celda queda vacía

---

### [2026-03-20] Creación de How-To.md

> Crea un archivo How-To.md en donde documentaremos ciertos procesos manuales. En esta creación y primera iteración, agrega una seccion con el encabezado "Adding new companies to the list" y explica el paso por paso que debe seguir un humano para agregar una company a la app web.

- Creado `How-To.md` en la raíz del proyecto como documento de referencia para procesos manuales
- Añadida sección **"Adding new companies to the list"** con:
  - Paso 1: cómo encontrar el CIK de una empresa en SEC EDGAR, con tip sobre reincorporaciones
  - Paso 2: cómo editar `companies.json` con formato correcto, ejemplo incluido y reglas de validación
  - Paso 3: cómo verificar que la nueva empresa aparece y carga correctamente en la app

---

### [2026-03-20] Multi-empresa: lista de tickers y barra de búsqueda

> Me gustaría tener un archivo en el cual listar una serie de empresas (ticker) y que al ejecutar la app se haga con cada una de ellas lo mismo que se hizo con ABT, obtener los datos publicos para armar la tabla de income statemente. Luego la app web tiene que tener arriba del todo una barra de busqueda que me permita cambiar a la tabla de la empresa que yo quiera dentro de esa misma lista. Para empezar podriamos listar estas 3 empresas primero. Abbot Laboratories (ABT), Medtronic plc (MDT) y Boston Scientific Corporation (BSX).

- Creado `TradingAppWeb/companies.json`: archivo editable con la lista de empresas (ticker, nombre, CIK de SEC EDGAR)
- Verificados los CIKs de las tres empresas contra la API de SEC EDGAR
- Generalizado `data.py`:
  - `fetch_and_cache(ticker, cik)` y `load_data(ticker, cik)` ahora aceptan cualquier empresa
  - Cache por empresa: `cache_ABT.json`, `cache_MDT.json`, `cache_BSX.json`
  - Corregida la función `_annual`: ahora **merges** datos de todos los conceptos XBRL en lugar de parar en el primero con datos, con prioridad al concepto más moderno (fix crítico para BSX que reporta revenues con dos conceptos distintos según el año)
  - Reordenados conceptos de `revenues` y `cogs` para dar prioridad al estándar ASC 606
- Actualizado `app.py`:
  - Nueva ruta `/company/<ticker>` para cada empresa
  - Ruta `/` redirige a la primera empresa de la lista
  - Ruta `/refresh/<ticker>` refresca solo la empresa activa
  - `build_table()` extraído como función reutilizable
- Actualizado `templates/index.html`:
  - Barra sticky superior con input de búsqueda y chips por empresa
  - Filtrado en tiempo real por ticker o nombre con JavaScript
  - Chip activo resaltado según empresa visualizada
  - Título y botón Refresh actualizados dinámicamente por empresa

---

### [2026-03-20] Corrección del cálculo de Gross Profit

> Ahora vamos a corregir un error en la tabla de IncomeStatement. La fila de Gross Profit no se esta mostrando correctamente. Asegurate de que el calculo de dicho valor sea Gross Profit = (total revenues - Cost of Goods Sold)

- Identificado que Abbott no reporta `GrossProfit` como concepto XBRL independiente (devolvía `N/A` para todos los años)
- Eliminado el uso de `s["gross_profit"]` de la serie XBRL en `app.py`
- Añadida variable `gross_profit` calculada explícitamente como `revenues - cogs` para cada año disponible
- Actualizadas las filas de Gross Profit, YoY % y % Gross Margins para usar el valor calculado

---

### [12:45] Reordenamiento del Changelog

> Genial! Un pequeño cambio, re ordenalos del más reciente al más viejo. Y cada prompt nuevo tiene que estar al principio del documento.

- Reordenadas todas las entradas del `Changelog.md` de más reciente a más antigua
- Los nuevos prompts se añadirán siempre al principio del documento

---

### [12:30] Creación del Changelog

> A partir de ahora crea un archivo "Changelog.md" en donde haras entrada con la fecha y hora, copies y pegues mi prompt como una quote y hagas una lista de los cambios realizados.

- Creado este archivo `Changelog.md` en la raíz del proyecto
- Documentados retroactivamente todos los cambios de la sesión inicial

---

### [12:00] Archivo ejecutable

> Crees que podrias crearme un archivo ejecutable que levante el servidor y una vez levantado me abra localhost 5000?

- Creado `launch.py` en la raíz del proyecto:
  - Lanza Flask como subprocess apuntando a `TradingAppWeb/app.py`
  - Hace polling cada 500 ms hasta que el servidor responde (timeout 30 s)
  - Abre automáticamente el navegador en `http://localhost:5000`
  - Captura `Ctrl+C` para terminar el proceso limpiamente
- Creado `Iniciar App.bat`: doble click para ejecutar `launch.py` desde cualquier ubicación, mantiene la consola abierta al finalizar

---

### [11:30] Integración de datos reales de Abbott (ABT)

> Eres capaz de hacer que los valores mostrados en la tabla se actualicen con los verdaderos valores publicos de una empresa que cotiza en bolsa? Intenta hacerlo con la accion de Abbot Laboratories (ABT), obten al menos los ultimos 10 años de datos y agrega el nombre de la empresa como titulo a la tabla.

- Creado `TradingAppWeb/data.py`: módulo de fetching desde la **SEC EDGAR XBRL API** (gratuita, sin API key)
  - Función `fetch_and_cache()`: descarga el JSON de hechos XBRL del CIK de Abbott (`0000001800`)
  - Función `load_data()`: sirve desde caché diario (`cache_abt.json`), refresca si es un nuevo día
  - Extrae 16 series financieras anuales filtrando entradas `10-K / FY`
- Reescrito `TradingAppWeb/app.py`:
  - Usa `data.py` para obtener datos reales
  - Calcula series derivadas: COGS negativo, Total Opex, EBITDA, Effective Tax Rate, YoY %, márgenes
  - Columnas dinámicas con los últimos 10 años fiscales disponibles (2016–2025)
  - Nuevo endpoint `/refresh` que fuerza un nuevo fetch desde SEC
- Actualizado `templates/index.html`:
  - Título dinámico: nombre de la empresa desde la API
  - Subtítulo con fuente (SEC EDGAR) y fecha de última actualización
  - Botón "Refresh Data" con ícono SVG
  - Columna del año más reciente resaltada en amarillo

---

### [11:00] Reorganización en subdirectorio

> Por favor mueve todos los archivos relacionados a la app web a un directorio interno /TradingAppWeb

- Creado directorio `TradingAppWeb/`
- Movidos `app.py` y `templates/index.html` a `TradingAppWeb/`
- Eliminado directorio `templates/` de la raíz
- Actualizada ruta del Excel en `app.py`: `"IncomeStatement.xlsx"` → `"../IncomeStatement.xlsx"`

---

### [10:30] Creación de la web app

> Podrias crear una app web en donde visualizar la tabla que creaste de IncomeStatement?

- Instalada librería `flask`
- Creado `app.py`: servidor Flask que lee `IncomeStatement.xlsx` con openpyxl y construye la tabla
- Creado `templates/index.html`: tabla con diseño dark mode
  - Filas coloreadas por tipo (totales, porcentajes, separadores de sección)
  - Valores positivos en verde, negativos en rojo
  - Columna LTM resaltada en amarillo
  - Header y columna de labels fijos al hacer scroll
- Corregido bug: `row.values` en Jinja2 resolvía al método `dict.values` — cambiado a `row['values']`
- App disponible en `http://localhost:5000`

---

### [10:00] Creación del spreadsheet

> Read the IncomeStatementExample.txt and create the corresponding spreadsheet

- Leído `IncomeStatementExample.txt` con datos del Income Statement de TIKR.com
- Instalada librería `openpyxl`
- Creado script `create_income_statement.py` que genera el Excel
- Generado `IncomeStatement.xlsx` con:
  - Encabezado con fondo azul marino y columnas: 31/12/21 → LTM
  - Filas con estilos diferenciados (bold, itálica, colores) según tipo de métrica
  - Formato numérico con separadores de miles y porcentajes
  - Paneles fijos (freeze panes) en B2
