# Model cards

One card per released model, or candidate for release (`<model-id>.md`), updated on every promotion.

| Card | Status |
|---|---|
| [`outlook-gbdt`](outlook-gbdt.md) | candidate for v0.1 |
| [`departure-gbdt`](departure-gbdt.md) | research model, not planned for v0.1 |

Use these headings:

1. **Target and horizon.** What is predicted, for which flights, and how far ahead.
2. **Training data.** Sources, time window, exclusions and regime flags.
3. **Features.** Inputs, with their knowledge-time rules.
4. **Evaluation.** Rolling-origin backtest design; Brier/CRPS skill against climatology; calibration (reliability diagram); interval coverage; results by regime (GDP/ground-stop, convective, snow, holiday).
5. **Intended use and limitations.** Who should use it for what, and what it must not be used for.
6. **Monitoring.** Live metrics, drift checks and the fallback model.
