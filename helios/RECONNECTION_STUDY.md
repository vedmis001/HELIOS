# HELIOS Co-Simulation — Datacenter Fault-Trip & Reconnection Study

## 1. Study Overview & Physical Motivation

In high-power modern data centers (150 MW+) tied directly to transmission or sub-transmission corridors (e.g. 161 kV PCC at Bus 5385 `DALLAS 3 1` in the ACTIVSg2000 Texas Grid), a severe grid fault triggers undervoltage protection. Server power distribution units, active front-end rectifiers, and variable-frequency drives (VFDs) for chiller plants disconnect or enter a protective trip state.

Once the fault is cleared by transmission protection, the transmission voltage recovers. The facility then executes an automatic reconnection / load pick-up sequence.

### Why Co-Simulation Is Required
- **Transient Stability (PSS/E, 10 ms)** cannot model the sub-cycle electromagnetic inrush currents, DC-link capacitor pre-charging transients, or fast phase-locked loop (PLL) acquisition dynamics during breaker closing.
- **Electromagnetic Transients (PSCAD, 0.5 µs)** cannot model the bulk Texas grid's 2000-bus power flow, multi-machine inertia, inter-area oscillation damping, or slow secondary voltage swings caused by synchronous machine AVRs.
- **The Co-Simulation Challenge**: Sudden disconnection drops 150 MW / 30.6 MVAR of load, accelerating local generation. Sudden reconnection injects a massive 150 MW step or ramp back into a recovering grid, risking secondary voltage collapse or trip re-triggering.

### Role of the Learned Adaptive Scheduler
The online Recursive Least Squares (RLS) surrogate (`learned_scheduler.py`) tracks active/reactive power as a function of voltage deviations.
1. **Pre-Fault Quiescent**: High surrogate confidence -> scheduler expands $\Delta t \to 50\text{--}80\text{ ms}$, bypassing EMT calls (`skip_emt=True`).
2. **Fault Inception ($t = 1.0\text{ s}$)**: Voltage collapses to $< 0.70\text{ pu}$ -> surrogate prediction error and epistemic uncertainty spike -> scheduler drops $\Delta t \to 2\text{ ms}$ and forces EMT execution.
3. **Tripped State ($t = 1.02\text{ s} \to 2.0\text{ s}$)**: Datacenter draws $P \approx 0, Q \approx 0$ -> RLS updates rapidly, uncertainty settles, $\Delta t$ expands.
4. **Reconnection Moment ($t = 2.0\text{ s}$)**: Discontinuity in $P, Q$ -> uncertainty spikes -> scheduler immediately contracts $\Delta t$ back to 2 ms to capture the inrush without numerical divergence.

---

## 2. Study Matrix

| Case ID | Name | Disturbance | Datacenter Response | Reconnection Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Case A** | Instantaneous Step | 3-phase fault at Bus 5385 from $t=1.0\text{ s}$ to $1.0833\text{ s}$ (5 cycles) | Undervoltage trip ($V < 0.70\text{ pu}$), $P \to 0, Q \to 0$ | Direct breaker re-close at $t = 2.0\text{ s}$ with unmitigated inrush surge ($1.3 \times P_0, 2.2 \times Q_0$ decaying over $\tau = 35\text{ ms}$). |
| **Case B** | Staged Soft Ramp | Same fault & UV trip | Tripped state until $t = 2.0\text{ s}$ | Controlled 3-stage / linear soft-start ramp over $T_{\text{ramp}} = 400\text{ ms}$ to mitigate secondary voltage drop. |
| **Case C** | Adverse Second-Swing Reconnection | Same fault & UV trip | Tripped state until $t = 1.35\text{ s}$ | Reconnection triggered directly into the nadir of the grid's second voltage swing to test ride-through boundaries. |

---

## 3. Implemented Modifications

### A. PSCAD Federate (`helios/helios_pscad_federate.py`)
1. **Protection & Reconnection State Machine in `stub_step_datacenter`**:
   - Added `status` state tracking: `"NORMAL"` $\to$ `"TRIPPED"` $\to$ `"RECONNECTING"` $\to$ `"NORMAL"`.
   - **Trip logic**: Voltage depression below `trip_v_threshold` (default 0.70 pu) lasting $> 1$ cycle (16 ms) triggers trip ($P \to 0, Q \to 0$).
   - **Reconnection logic**: At $t \ge t_{\text{reconnect}}$ (default 2.0 s), transitions to `"RECONNECTING"`.
     - In `instantaneous` mode: injects exponential inrush surge decaying over 35 ms.
     - In `staged_ramp` mode: smooth linear / multi-block ramp over `reconnect_ramp_s` (default 0.40 s).
2. **Configurable Parameters via Environment Variables & Function Arguments**:
   - `HELIOS_RECONNECT_MODE`: `"instantaneous"`, `"staged_ramp"`, or `"none"` (default: `"staged_ramp"`).
   - `HELIOS_TRIP_V_THRESHOLD`: Undervoltage trip threshold (default: `0.70` pu).
   - `HELIOS_RECONNECT_TIME_S`: Reconnection timestamp (default: `2.0` s).
   - `HELIOS_RECONNECT_RAMP_S`: Soft-start ramp duration (default: `0.40` s).

### B. PSS/E Federate (`helios/helios_psse_federate.py`)
1. **Fault Disturbance Scheduling**:
   - Injected PSS/E 3-phase bus fault using `psspy.dist_bus_fault(BOUNDARY_BUS, 1, 0.0, [0.0, -20000.0])` at `FAULT_START_S` ($1.0\text{ s}$).
   - Cleared fault using `psspy.dist_clear_fault(1)` at `FAULT_CLEAR_S` ($1.0833\text{ s}$).
2. **Scheduler Awareness**:
   - Populated `ScenarioContext.event_times = [FAULT_START_S, FAULT_CLEAR_S, RECONNECT_TIME_S]`.
   - Enables the adaptive policy to anticipate the exact event boundaries, preventing time-step overshoot and ensuring fine 2 ms resolution right at fault inception, fault clearing, and datacenter reconnection.
3. **Environment Variable Overrides**:
   - `HELIOS_FAULT_ENABLE`: Toggle fault (`1` or `0`, default `1`).
   - `HELIOS_FAULT_START_S`: Start time (default `1.0` s).
   - `HELIOS_FAULT_CLEAR_S`: Clearing time (default `1.0833` s).
   - `HELIOS_RECONNECT_TIME_S`: Reconnection time (default `2.0` s).

### C. Synthetic Grid Backend (`helios/ts_backend.py`)
- Updated `SyntheticGridBackend` to support fault clearing and reconnection event registration, providing a fast standalone test harness for parameter sweeps without requiring full PSS/E license or GUI session.

### D. Study Runner & Automated Plotter (`helios/run_reconnection_study.py`)
- Implemented automated comparative testbench comparing:
  - Fixed 10 ms baseline vs. Learned Adaptive.
  - Case A (Instantaneous Step) vs. Case B (Staged Ramp).
- Generates publication-ready metrics summary and comparison plots.

---

## 4. How to Run the Study

### Running with Full PSS/E + PSCAD via HELICS
Set the desired reconnection mode and execute through `helics`:

```powershell
# For Case B (Staged Soft-Start Ramp):
$env:HELIOS_RECONNECT_MODE = "staged_ramp"
$env:HELIOS_RECONNECT_TIME_S = "2.0"
$env:HELIOS_RECONNECT_RAMP_S = "0.40"
helics run --path=helios_runner.json

# For Case A (Instantaneous Step with Inrush):
$env:HELIOS_RECONNECT_MODE = "instantaneous"
$env:HELIOS_RECONNECT_TIME_S = "2.0"
helics run --path=helios_runner.json
```

### Running Standalone Study Runner (Quick Synthetic Benchmark)
```powershell
python run_reconnection_study.py --cases step ramp
```
