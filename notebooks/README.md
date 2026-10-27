# Notebooks

Exploratory analysis only.

- Name notebooks `NN_topic.ipynb` (e.g. `01_bts_overview.ipynb`).
- Outputs are stripped by pre-commit.
- Move reusable code into `src/ordfi/`. Charts use `ordfi.viz` (the validated palette and theme).
- Read data from `data/`; never embed credentials.

| Notebook | Contents | Needs |
|---|---|---|
| `01_ord_delays_overview.ipynb` | First look at ORD delays: coverage, yearly trend, season × hour, weather, FAA programs, inbound aircraft, carriers | `make dbt-build` |
