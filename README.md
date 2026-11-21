# HELIOS: Hybrid Adaptive TS–EMT Co-Simulation & Component Validation Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**HELIOS** is an open-source co-simulation and electromagnetic transient (EMT) validation framework designed to study high-power, inverter-dominated loads—such as hyperscale datacenters—interconnected to bulk transmission grids.

Traditional power system workflows split **Transient Stability (TS)** (e.g., PSS/E at millisecond steps) and **Electromagnetic Transients (EMT)** (e.g., PSCAD at microsecond steps) into isolated silos. HELIOS bridges these domains over **HELICS** with an **online Recursive Least Squares (RLS) surrogate & adaptive time-step scheduler**, allowing researchers to capture both device-scale power-electronic inrush/protection physics and bulk-grid generator inertia/voltage stability in a single coupled study.

---

## Repository Structure

```text
helios_cosim/
├── README.md                                  # Project overview, navigation guide, and quick start
├── LICENSE                                    # MIT Open Source License
├── .gitignore                                 # Git ignore rules for caches, logs, and binary dumps
│
├── helios/                                    # 1. Adaptive TS–EMT Co-Simulation Engine (HELICS)
│   ├── config/
│   │   └── helios_runner.json                 # HELICS federation manifest (broker + PSSE + PSCAD)
│   ├── core/
│   │   ├── scheduler/
│   │   │   └── learned_scheduler.py           # Adaptive time-step controller & online RLS surrogate
│   │   ├── backends/
│   │   │   └── ts_backend.py                  # Pluggable TS backends (PSSE, TSAOpt, Synthetic, Stiff)
│   │   └── nl_engine/
│   │       └── claude_nl_engine.py            # Natural-language scenario configuration engine
│   ├── federates/
│   │   ├── broker/
│   │   │   └── helios_broker.py               # Standalone HELICS broker launcher
│   │   ├── ts/
│   │   │   ├── helios_psse_federate.py        # Siemens PSS/E TS federate (ACTIVSg2000 Bus 5385)
│   │   │   └── helios_ts_federate.py          # Generic TS federate (Synthetic, TSAOpt, Stiff)
│   │   └── emt/
│   │       └── helios_pscad_federate.py       # PSCAD EMT federate (ComFab socket + datacenter model)
│   ├── runners/
│   │   └── run_adaptive_cosim.py              # In-process HELICS co-simulation orchestrator
│   ├── studies/
│   │   └── reconnection/
│   │       ├── run_reconnection_study.py      # 3-way benchmark: Co-Sim Step vs. Ramp vs. Stiff Grid
│   │       ├── plot_results.py                # High-clarity adaptive-axis waveform plotter
│   │       └── RECONNECTION_STUDY.md          # Technical guide for the datacenter reconnection study
│   └── results/
│       ├── figures/                           # Publication & telemetry waveform plots (.png)
│       ├── data/                              # Benchmark timeseries outputs (.json)
│       └── logs/                              # Saved federate telemetry logs
│
├── component_sim/                             # 2. Standalone EMT Component Simulator & PSCAD Validation
│   ├── README.md                              # Component simulator quick-start guide
│   ├── run.py                                 # CLI entry point for JSON-configured EMT simulations
│   ├── core/                                  # Sparse Modified Nodal Analysis (MNA) & adaptive stepping
│   │   ├── circuit.py                         # Netlist parser & element registry
│   │   ├── elements.py                        # Fundamental R, L, C, and independent source stamps
│   │   ├── simulator.py                       # Implicit trapezoidal / BE time-domain solver
│   │   ├── sparse.py                          # Sparse linear system solver
│   │   └── adaptive.py                        # Fixed, PSCAD-style LTE, and agentic Claude controllers
│   ├── components/                            # Physics-based power-system & datacenter component models
│   │   ├── transformer.py                     # Coupled magnetic transformer model
│   │   ├── battery.py                         # Energy storage / UPS battery model
│   │   ├── buckboost.py                       # Switched DC-DC buck-boost converter model
│   │   └── machine.py                         # Induction machine model
│   ├── configs/                               # Ready-to-run JSON testbeds (RC, RL, RLC, UPS slice, etc.)
│   ├── tests/                                 # Unit tests & adaptive stepping benchmarks
│   ├── validation/                            # Ground-truth PSCAD comparison & figure generation
│   │   ├── compare_pscad.py                   # Compares Python EMT traces against PSCAD .psout / .out
│   │   └── generate_slide_figures.py          # Generates publication/presentation validation figures
│   └── results/
│       ├── data/                              # Saved validation CSV traces
│       └── figures/
│           ├── components/                    # Per-component verification waveforms
│           ├── benchmarks/                    # Adaptive vs. fixed stepping benchmark plots
│           └── slides/                        # Presentation & paper figures
│
└── tsaopt/                                    # 3. Differentiable Transient Stability & Optimization
    ├── tsaopt.py                              # CLI entry point (simulate, optimize-direct, optimize-modular)
    ├── models/
    │   ├── dynamic/                           # Synchronous machines, exciters, governors, controllers
    │   └── static/                            # Buses, lines, transformers, loads
    └── scripts/
        ├── compile_sympy.py                   # Symbolic Jacobian & residual compiler
        ├── timestep_control.py                # Adaptive TS timestep logic
        └── solvers/                           # Implicit DAE numerical solvers
```

---

## Context & Key Capabilities

1. **Co-Simulation Engine (`helios/`)**
   - **Why Co-Simulation?** Standalone EMT (PSCAD on an infinite bus) misses bulk-grid voltage sags and frequency nadirs; standalone TS (PSS/E with static loads) misses sub-cycle converter inrush and protection tripping. HELIOS couples both domains dynamically.
   - **Adaptive RLS Surrogate Scheduling (`helios/core/scheduler/`)**: During quasi-steady periods, the online RLS surrogate predicts boundary $P/Q$ injections and safely bypasses expensive EMT calls while tightly clamping step sizes around faults, breaker trips, and reconnections.
   - **Datacenter Reconnection Benchmark (`helios/studies/reconnection/`)**: Compares instantaneous breaker reclosure vs. 400 ms staged soft-start ramping vs. standalone stiff-grid EMT (see [`RECONNECTION_STUDY.md`](helios/studies/reconnection/RECONNECTION_STUDY.md)).

2. **EMT Component Simulator & Validation (`component_sim/`)**
   - Provides a lightweight, transparent Python MNA circuit solver to prototype and validate individual datacenter/grid components (transformers, UPS slices, buck-boost converters, batteries, induction machines).
   - Includes automated validation utilities (`component_sim/validation/compare_pscad.py`) to compute RMSE / max error against PSCAD `.psout` and legacy `.inf`/`.out` ground-truth traces.
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
python helios/studies/reconnection/run_reconnection_study.py
```

Outputs are automatically written to `helios/results/data/` (JSON) and `helios/results/figures/helios_reconnection_comparison.png`.

To run the live **PSS/E + PSCAD** HELICS federation (requires PSS/E and PSCAD configured on Windows):

```bash
cd helios
helics run --path=config/helios_runner.json
python studies/reconnection/plot_results.py
```

See [`helios/studies/reconnection/RECONNECTION_STUDY.md`](helios/studies/reconnection/RECONNECTION_STUDY.md) for environment variables (`HELIOS_RECONNECT_MODE`, `HELIOS_RECONNECT_TIME_S`, `HELIOS_RECONNECT_RAMP_S`) and detailed setup.

---

### 2. Run the EMT Component Simulator & Validation Suite
Run any circuit testbed from `component_sim/`:

```bash
cd component_sim

# Run a basic RLC or UPS slice simulation with plots
python run.py --config configs/rlc_test.json --mode compare --plot
python run.py --config configs/ups_slice_test.json --mode pscad --plot

# Compare Python EMT traces against PSCAD output
python validation/compare_pscad.py --pscad path/to/case.psout --sim results/data/ups_slice.csv
```

---

### 3. Run the `tsaopt` Transient Stability Solver
```bash
cd tsaopt
python tsaopt.py simulate --help
```

---

## Use of Generative AI

Generative AI tools were used in two distinct capacities in this repository:

1. **Software Engineering & Documentation Assistance:** Coding assistants were used to help scaffold modules, debug numerical solver and IPC/socket edge cases, refactor the repository structure, generate comparative plotting scripts, and draft documentation. All physical modeling assumptions, power-system formulations, and simulation results were created, reviewed, and verified by the author.
2. **In-Loop Agentic Simulation Features:** The framework itself explores LLM-assisted workflows via [`claude_nl_engine.py`](helios/core/nl_engine/claude_nl_engine.py) (translating natural-language study descriptions into structured scenario JSONs) and `ClaudeTimeStepAgent` in [`component_sim/core/adaptive.py`](component_sim/core/adaptive.py) (experimenting with agentic adaptive time-step control). Core physics solvers and HELICS co-simulation run completely offline without requiring any LLM API access.

---

## Acknowledgements

We would like to thank Tim McNamara, Professor Larry Pileggi, and other lab members. 
---

## References

1. **HELICS Co-Simulation Framework:** B. Palmintier, D. Krishnamurthy, P. Top, S. Smith, J. Daily, and J. Fuller, *"Design of the HELICS High-Performance Transmission-Distribution-Communication-Market Co-Simulation Framework,"* in *2017 Workshop on Modeling and Simulation of Cyber-Physical Energy Systems (MSCPES)*, IEEE, 2017, pp. 1–6. [https://helics.org](https://helics.org)
2. **ACTIVSg2000 Synthetic Texas Grid:** A. B. Birchfield, T. Xu, K. M. Gegner, K. S. Shetye, and T. J. Overbye, *"Grid Structural Characteristics as Validation Criteria for Synthetic Networks,"* *IEEE Transactions on Power Systems*, vol. 32, no. 4, pp. 3258–3265, July 2017. (Texas A&M University Electric Grid Test Case Repository: [https://electricgrids.engr.tamu.edu](https://electricgrids.engr.tamu.edu))
3. **Modified Nodal Analysis (MNA):** C.-W. Ho, A. E. Ruehli, and P. A. Brennan, *"The Modified Nodal Approach to Network Analysis,"* *IEEE Transactions on Circuits and Systems*, vol. 22, no. 6, pp. 504–509, June 1975.
4. **EMT & Transient Stability Simulators:**
   - Manitoba Hydro International Ltd., *PSCAD™ / EMTDC™ Electromagnetic Transients Simulation Software & Co-Simulation Interface (ComFab / `mhi.psout`)*. [https://www.pscad.com](https://www.pscad.com)
   - Siemens PTI, *PSS®E — High-Performance Transmission Planning and Analysis Software*.
5. **Large-Load & Datacenter Grid Reliability:** North American Electric Reliability Corporation (NERC), *Large Loads Task Force (LLTF) — Characteristics and Risks of Emerging Large Loads*, Technical Reports and Interconnection Reliability Assessments. [https://www.nerc.com](https://www.nerc.com)

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
