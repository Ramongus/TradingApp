# CLAUDE.md – TradingApp

Instrucciones permanentes para Claude Code en este proyecto. Estas reglas se aplican en toda sesión.

---

## Changelog

- Cada vez que el usuario haga un pedido y se realicen cambios, agregar una nueva entrada al inicio de `DesignDocuments/Changelog.md`.
- Formato de cada entrada:
  ```
  ### [YYYY-MM-DD] Título descriptivo del cambio

  > Prompt literal del usuario (como blockquote)

  - Lista de cambios realizados, archivo por archivo
  ```
- Las entradas nuevas siempre van al **principio** del archivo, debajo del título.

---

## Reglas de desarrollo

- **Máxima información pública:** siempre traer la mayor cantidad de datos disponibles desde SEC EDGAR. Si una empresa no reporta un campo, la celda queda vacía — nunca omitir la fila entera.
- **Datos 100% reales:** los valores mostrados en las tablas deben ser capturados exactamente como están publicados. Los campos calculados deben estar claramente identificados como tales.
- **Sincronización compare ↔ single-company:** cualquier fila que se agregue a una tabla de vista individual (`build_balance_sheet_table`, `build_cf_table`, `build_table`) debe agregarse también a la lista de métricas correspondiente en la vista de comparación (`_BS_COMP_METRICS`, `_CF_COMP_METRICS`, `_COMP_METRICS`).
- **Soporte IFRS:** empresas que reportan bajo IFRS (emisores extranjeros con 20-F) son detectadas automáticamente en `data.py` comparando el tamaño de los namespaces `ifrs-full` vs `us-gaap`. No requieren configuración manual.

---

## Estructura del proyecto

```
TradingApp/
├── CLAUDE.md                     ← este archivo
├── launch.py                     ← arranca el servidor y abre el browser
├── Iniciar App.bat               ← acceso rápido para Windows
├── DesignDocuments/
│   ├── Changelog.md              ← historial de cambios por prompt
│   ├── How-To.md                 ← procesos manuales
│   └── *.txt / *.xlsx            ← ejemplos de referencia
└── TradingAppWeb/
    ├── app.py                    ← servidor Flask, rutas, build_table()
    ├── data.py                   ← fetch SEC EDGAR, caché, series IFRS/GAAP
    ├── prices.py                 ← precios via yfinance
    ├── companies.json            ← lista de empresas (ticker, name, cik)
    ├── cache_*.json              ← caché por empresa y precios
    └── templates/
        ├── index.html            ← vista individual
        └── compare.html         ← vista de comparación multi-empresa
```
