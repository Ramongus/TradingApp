# Changelog – TradingApp

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
