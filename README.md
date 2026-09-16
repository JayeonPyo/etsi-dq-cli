# ETSI Data Quality Validation Tool — CLI

A lightweight, scriptable **command-line interface** for the ETSI `etsi_dq` data-quality engine.
It evaluates a tabular dataset against six ETSI TR 104 180 metrics — **Completeness, Accuracy,
Consistency, Timeliness, Reliability, Uniqueness** — and can issue a verifiable certificate.

The CLI does **not** re-implement the scoring logic. It calls the same `etsi_dq` core library that
the web dashboard uses, so **given the same rules it produces identical results**.

---

## What's in this repository

```
etsi-dq-cli/
├── etsi-dq/                     # The CLI (this project)
├── etsi-dq-lib/                # ETSI etsi_dq core library + dashboard (see Attribution)
├── amazon_delivery.csv         # Demo dataset (43,739 rows)
├── delivery_time_reference.csv # Reference file for the accuracy rule
├── valid_categories.csv        # Valid-list file for the consistency rule
└── rules.json                  # Example configuration (matches the dashboard demo)
```

---

## Requirements

- Python 3.10+
- Node.js 18+ (only if you also want to run the dashboard frontend)

---

## Install

```bash
git clone https://github.com/JayeonPyo/etsi-dq-cli.git
cd etsi-dq-cli
pip install -e "./etsi-dq[all]"
```

The CLI locates the `etsi_dq` core library in `etsi-dq-lib/` automatically, as long as you run
commands from the repository root. If you move things around, point to the library explicitly:

```bash
export ETSI_DQ_LIB=/path/to/etsi-dq-lib
```

---

## Quick start

Run everything from the repository root (where the CSV files live).

```bash
# 1. Register (once) — links each evaluation to a user
etsi-dq register --name "Your Name" --org "Your Org"

# 2. Configure the metrics interactively (like the dashboard)
etsi-dq configure amazon_delivery.csv

# 3. Run the full assessment
etsi-dq check amazon_delivery.csv --config rules.json
```

Expected result on the demo data:

```
  Overall: 89.2%  (B)
  completeness 100.0% · accuracy 95.0% · consistency 100.0%
  timeliness 100.0% · reliability 41.6% · uniqueness 100.0%
```

Run a single metric, or inspect details:

```bash
etsi-dq check amazon_delivery.csv --config rules.json --metrics reliability
etsi-dq check amazon_delivery.csv --config rules.json --format json
```

---

## Certificates (optional)

Certificate issuing and verification need the backend server running. In a separate terminal:

```bash
cd etsi-dq-lib
uvicorn api.main:app --port 8000
```

Then a full run (without `--no-submit`) issues a signed certificate:

```bash
etsi-dq check amazon_delivery.csv --config rules.json
etsi-dq verify DQ-2026-...          # verify by ID
etsi-dq history                     # list past evaluations
```

The output prints a `PDF:` link you can open in a browser to view the signed certificate.

---

## Configuration

`etsi-dq configure` builds a `rules.json` interactively by listing your columns and letting you
choose how each metric is checked. You can also edit `rules.json` by hand:

- **accuracy** — reference-file comparison (with tolerance) or a numeric range
- **consistency** — referential integrity (valid-list file) or an expression
- **timeliness** — event/system time columns + SLA in seconds
- **reliability** — numeric column(s), coefficient of variation
- **uniqueness_keys** — key columns for duplicate detection

---

## Attribution

`etsi-dq-lib/` contains the ETSI `etsi_dq` core library and reference dashboard, developed as an
ETSI Proof of Concept and published at the ETSI Labs repository:

> https://labs.etsi.org/rep/data/poc/data-quality-assessment

It is included here for convenience and reproducibility, and remains subject to its own license and
terms. The CLI in `etsi-dq/` is the contribution of this repository.

---

## License

The CLI (`etsi-dq/`) is released under the MIT License (see `LICENSE`). The bundled `etsi-dq-lib/`
is the property of ETSI and is governed by its own license.
