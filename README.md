# HELIOS: Hybrid Adaptive TS–EMT Co-Simulation & Component Validation Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**HELIOS** is an open-source co-simulation and electromagnetic transient (EMT) validation framework designed to study high-power, inverter-dominated loads—such as hyperscale datacenters—interconnected to bulk transmission grids.

Traditional power system workflows split **Transient Stability (TS)** (e.g., PSS/E at millisecond steps) and **Electromagnetic Transients (EMT)** (e.g., PSCAD at microsecond steps) into isolated silos. HELIOS bridges these domains over **HELICS** with an **online Recursive Least Squares (RLS) surrogate & adaptive time-step scheduler**, allowing researchers to capture both device-scale power-electronic inrush/protection physics and bulk-grid generator inertia/voltage stability in a single coupled study.

---

## Repository Structure

```text
helios_cosim/
├── README.md                              # Project overview, navigation guide, and quick start
├── LICENSE                                # MIT Open Source License
├── .gitignore                             # Git ignore rules for caches, logs, and binary dumps
│
├── helios/                                # 1. Adaptive TS–EMT Co-Simulation Engine (HELICS)
│   ├── helios_runner.json                 # HELICS federation manifest (broker + PSSE + PSCAD)
│   ├── helios_broker.py                   # Standalone HELICS broker launcher
│   ├── helios_psse_federate.py            # PSS/E Transient Stability federate (ACTIVSg2000 Bus 5385)
│   ├── helios_pscad_federate.py           # PSCAD EMT federate (ComFab TCP socket + dynamic datacenter model)
│   ├── helios_ts_federate.py              # Generic TS federate supporting Synthetic, TSAOpt, and Stiff backends
│   ├── ts_backend.py                      # Modular TS backends (PSSE, TSAOpt, SyntheticGrid, StiffGrid)
│   ├── learned_scheduler.py               # Adaptive time-step controller & online RLS boundary surrogate
│   ├── claude_nl_engine.py                # Natural-language scenario & parameter configuration engine
│   ├── run_adaptive_cosim.py              # In-process HELICS co-simulation runner
│   ├── run_reconnection_study.py          # 3-way benchmark: Co-Sim Step vs. Co-Sim Ramp vs. Stiff Grid
│   ├── plot_results.py                    # High-clarity adaptive-axis waveform plotter
│   ├── RECONNECTION_STUDY.md              # Detailed technical guide for the datacenter reconnection study
│   ├── helios_reconnection_comparison.png # Published 3-way reconnection comparison figure
│   └── helios_reconnection_plot.png       # Single-run adaptive telemetry plot
│
├── component_sim/                         # 2. Standalone EMT Component Simulator & PSCAD Validation Suite
│   ├── run.py                             # CLI entry point for JSON-configured EMT circuit simulations
│   ├── core/                              # Sparse Modified Nodal Analysis (MNA) & adaptive stepping engine
│   │   ├── circuit.py                     # Netlist parser & element registry
│   │   ├── elements.py                    # Fundamental R, L, C, and independent source stamps
│   │   ├── simulator.py                   # Implicit trapezoidal / BE time-domain solver
│   │   ├── sparse.py                      # Sparse linear system solver
│   │   └── adaptive.py                    # Fixed, PSCAD-style LTE, and agentic Claude step controllers
│   ├── components/                        # Physics-based power-system & datacenter component models
│   │   ├── transformer.py                 # Coupled magnetic transformer model
│   │   ├── battery.py                     # Energy storage / UPS battery model
│   │   ├── buckboost.py                   # Switched DC-DC buck-boost converter model
│   │   └── machine.py                     # Induction machine model
│   ├── configs/                           # Ready-to-run JSON testbeds (RC, RL, RLC, UPS slice, etc.)
│   ├── tests/                             # Unit tests & adaptive stepping benchmarks
│   ├── validation/                        # Ground-truth PSCAD comparison & figure generation scripts
│   │   ├── compare_pscad.py               # Compares Python EMT traces against PSCAD .psout / .out files
│   │   └── generate_slide_figures.py      # Generates publication/presentation validation figures
│   └── results/                           # Saved validation CSVs and benchmark waveform plots
│
└── tsaopt/                                # 3. Differentiable Transient Stability Analysis & Optimization
    ├── tsaopt.py                          # CLI entry point (simulate, optimize-direct, optimize-modular)
    ├── models/                            # SymPy-compiled dynamic & static power system models
    │   ├── dynamic/                       # Synchronous machines, exciters, governors, controllers
    │   └── static/                        # Buses, lines, transformers, loads
    └── scripts/                           # SymPy compilation, implicit solvers, and timestep control
        ├── compile_sympy.py               # Symbolic Jacobian & residual compiler
        ├── timestep_control.py            # Adaptive TS timestep logic
        └── solvers/                       # Implicit DAE numerical solvers
```

---

## Context & Key Capabilities

1. **Co-Simulation Engine (`helios/`)**
   - **Why Co-Simulation?** Standalone EMT (PSCAD on an infinite bus) misses bulk-grid voltage sags and frequency nadirs; standalone TS (PSS/E with static loads) misses sub-cycle converter inrush and protection tripping. HELIOS couples both domains dynamically.
   - **Adaptive RLS Surrogate Scheduling**: During quasi-steady periods, the online RLS surrogate predicts boundary $P/Q$ injections and safely bypasses expensive EMT calls while tightly clamping step sizes around faults, breaker trips, and reconnections.
   - **Datacenter Reconnection Benchmark**: Compares instantaneous breaker reclosure vs. 400 ms staged soft-start ramping vs. standalone stiff-grid EMT (see [`helios/RECONNECTION_STUDY.md`](helios/RECONNECTION_STUDY.md)).

2. **EMT Component Simulator & Validation (`component_sim/`)**
   - Provides a lightweight, transparent Python MNA circuit solver to prototype and validate individual datacenter/grid components (transformers, UPS slices, buck-boost converters, batteries, induction machines).
   - Includes automated validation utilities (`validation/compare_pscad.py`) to compute RMSE / max error against PSCAD `.psout` and legacy `.inf`/`.out` ground-truth traces.
   - Supports fixed stepping, Local Truncation Error (LTE) adaptive stepping, and LLM-guided (`claude`) adaptive stepping.

3. **Transient Stability Solver & Optimizer (`tsaopt/`)**
   - SymPy-based symbolic power system DAE solver and trajectory optimization framework that can run standalone or serve as an open-source TS backend inside HELIOS without requiring a commercial PSS/E license.

---

## High-Level Quick Start

### Prerequisites
- **Python 3.10+** (tested on Python 3.13)
- Core Python packages:
  ```bash
  pip install numpy scipy matplotlib sympy helics
  ```
- *Optional*:
  - **Siemens PSS/E** (`psspy`) & **PSCAD v5+** (`mhi.psout`, ComFab socket) for commercial co-simulation and `.psout` validation.
  - `anthropic` (with `ANTHROPIC_API_KEY` set) for natural-language scenario generation (`claude_nl_engine.py`) or agentic adaptive stepping (`--mode claude`).

---

### 1. Run the HELIOS Co-Simulation Reconnection Study
Run the 3-way benchmark (Instantaneous Step vs. Staged Soft-Start Ramp vs. No-TS Stiff Grid) in-process without needing PSS/E or PSCAD licenses:

```bash
cd helios
python run_reconnection_study.py
```

This generates the comparative metrics table, result JSON files, and `helios/helios_reconnection_comparison.png`.

To run the live **PSS/E + PSCAD** HELICS federation (requires PSS/E and PSCAD configured on Windows):

```bash
cd helios
helics run --path=helios_runner.json
python plot_results.py
```

See [`helios/RECONNECTION_STUDY.md`](helios/RECONNECTION_STUDY.md) for environment variables (`HELIOS_RECONNECT_MODE`, `HELIOS_RECONNECT_TIME_S`, `HELIOS_RECONNECT_RAMP_S`) and detailed setup.

---

### 2. Run the EMT Component Simulator & Validation Suite
Run any circuit testbed from `component_sim/`:

```bash
cd component_sim

# Run a basic RLC or UPS slice simulation with plots
python run.py --config configs/rlc_test.json --mode compare --plot
python run.py --config configs/ups_slice_test.json --mode pscad --plot

# Run the component unit tests
python -m unittest discover -s tests
```

To validate Python EMT traces against PSCAD output:

```bash
cd component_sim
python validation/compare_pscad.py --pscad path/to/case.psout --sim results/ups_slice.csv
```

---

### 3. Run the `tsaopt` Transient Stability Solver
```bash
cd tsaopt
python tsaopt.py simulate --help
```

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
