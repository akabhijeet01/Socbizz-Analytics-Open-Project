# Open Project 2026 — Agentic AI Dynamic Tariff Optimization

Agentic framework for EV charging demand forecasting and dynamic tariff optimization using **UrbanEV (ST-EVCDP)** and **ACN** datasets.

## Repository structure

```
├── main.py                 # Run full pipeline
├── config.py               # Tariff thresholds & assumptions
├── requirements.txt
├── src/                    # Preprocessing, models, agents
├── notebooks/analysis.ipynb
├── docs/OpenProject2026_Presentation.pptx
├── data/
│   ├── ACN/                # Place acndata_sessions.json.xlsx here
│   └── UrbanEV/            # Place UrbanEV CSVs here
└── outputs/                # Metrics & figures (after running main.py)
```

## Dataset setup

Download datasets and place them as follows:

**ACN** — [ev.caltech.edu/dataset.html](https://ev.caltech.edu/dataset.html)  
Copy `acndata_sessions.json.xlsx` to:
`data/ACN/acndata_sessions.json.xlsx`

**UrbanEV** — [github.com/IntelligentSystemsLab/ST-EVCDP](https://github.com/IntelligentSystemsLab/ST-EVCDP)  
Copy all CSVs (`occupancy.csv`, `volume.csv`, `price.csv`, `time.csv`, `information.csv`, etc.) to:
`data/UrbanEV/`

> If you already have the original folders (`ACN Data_...` and `UrbanEV_ SZ_districts`), the pipeline still reads those paths via `config.py`.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
python scripts/build_presentation.py   # regenerate slides
```

## Agents

| Agent | Dataset | Role |
|-------|---------|------|
| Demand + Tariff (merged) | UrbanEV + ACN | Forecast utilization, recommend dynamic tariffs |
| Monitoring & Learning | Both | Evaluate KPIs, feedback loop |

## Key results

| Metric | Value |
|--------|-------|
| RMSE / MAE / R² | 0.036 / 0.021 / 0.94 |
| Revenue gain % | -0.67% (consumer-friendly pricing) |
| Off-peak uplift | +1.11% |
| Wait reduction proxy | +1.35% |

## Presentation

See `docs/OpenProject2026_Presentation.pptx` (7 content slides + title).
