# HELIOS Component Simulator & PSCAD Validation (`component_sim/`)

This module provides a standalone Python **Modified Nodal Analysis (MNA)** electromagnetic transient (EMT) component simulator with fixed, PSCAD-style Local Truncation Error (LTE), and agentic (`claude`) adaptive time-stepping, alongside validation tools for comparing traces directly against PSCAD `.psout` / `.out` outputs.

> For the full project overview, see the root [README.md](../README.md).

## Directory Overview
- `run.py` — Main CLI entry point for JSON-configured circuit simulations.
- `core/` — Sparse MNA engine (`circuit.py`, `elements.py`, `simulator.py`, `sparse.py`) and adaptive step-size controllers (`adaptive.py`).
- `components/` — Power-system & datacenter component models (`transformer.py`, `battery.py`, `buckboost.py`, `machine.py`).
- `configs/` — JSON circuit configurations (`rc_test.json`, `rl_test.json`, `rlc_test.json`, `battery_test.json`, `buckboost_test.json`, `machine_test.json`, `transformer_test.json`, `ups_slice_test.json`).
- `tests/` — Unit tests and adaptive stepping benchmarks.
- `validation/` — PSCAD comparison (`compare_pscad.py`) and figure generation (`generate_slide_figures.py`).
- `results/` — Pre-generated benchmark outputs organized into `results/data/` (`.csv`) and `results/figures/` (`components/`, `benchmarks/`, `slides/`).

## Quick Usage

Run from inside `component_sim/`:

```bash
# Run a standard circuit simulation
python run.py --config configs/rc_test.json

# Compare fixed vs. adaptive stepping with plots
python run.py --config configs/rlc_test.json --mode compare --plot

# Run the UPS datacenter slice testbed
python run.py --config configs/ups_slice_test.json --mode pscad --plot

# Run unit tests
python -m unittest discover -s tests
```
