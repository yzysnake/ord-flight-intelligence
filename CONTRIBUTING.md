# Contributing

## Development setup

```bash
make env && conda activate ordfi
make install hooks
make check
```

After changing `environment.yml`, run `make env-update`, then `make lock` to regenerate `conda-lock.yml`. Commit both files together.

## Workflow

- **Trunk-based development.** `main` is always releasable. Work on short-lived branches named `<type>/<short-topic>`, for example `feat/bts-ingest` or `docs/adr-storage`, and merge through pull requests once CI passes.
- **Conventional Commits** for messages: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`, `perf:`.
- **Semantic version tags** for model and API releases.
- **Architecture decisions** are recorded in [`docs/adr/`](docs/adr/README.md) *before* they are implemented.

## Code standards

- Python 3.12, src layout, package `ordfi`.
- `ruff` (lint and format) and `mypy --strict` must pass. Pre-commit runs them on every commit.
- Every new module comes with tests. Time-handling and feature code also need property tests (`tests/property/`) that assert point-in-time correctness.
- Notebooks live in `notebooks/` with numbered names (`01_bts_overview.ipynb`). Outputs are stripped automatically. Once code is reused, move it into `src/ordfi/`.

## Data rules

1. **Never commit data, credentials or API responses.** `data/` and `.env` are git-ignored. Put secrets in `.env` (start from `.env.example`) or in GitHub Actions secrets.
2. **Every source needs a data-catalog card** ([`docs/data-catalog/`](docs/data-catalog/README.md)) before any code ingests it. The card records licence class, attribution text, retention limit and knowledge-time rule.
3. **Respect licence terms in code.** Retention limits are enforced with TTL deletion, providers that forbid mixing stay isolated, and attribution is shown wherever the data appears.
4. **Point-in-time correctness.** A feature for a prediction at time *t* may only use inputs with `known_time ≤ t`. Use archived forecasts, never observed weather, for future hours.

## Pull requests

Use the PR template checklist. A PR that adds a data source, a model, or a user-facing number should explain how it was validated.
