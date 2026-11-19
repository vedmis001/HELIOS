"""
run_reconnection_study.py
═══════════════════════════════════════════════════════════════════════════════
HELIOS Co-Simulation — Datacenter Fault-Trip & Reconnection Study Runner

Compares:
  - Case A: Instantaneous Step Reconnection (with unmitigated EMT inrush)
  - Case B: Staged Soft-Start Ramp Reconnection (controlled 400ms ramp)

Evaluates:
  1. Secondary voltage depression at 161 kV PCC (Bus 5385).
  2. Grid frequency deviation and inertia response.
  3. Learned Adaptive Scheduler response: RLS surprise, epistemic uncertainty,
     automatic step contraction (down to 2ms) and EMT bypass ratio.
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import copy
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple
import numpy as np

# Configure paths
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import helics as h
from helios_pscad_federate import run_cosim as run_pscad_loop
from helios_ts_federate import run_ts_federate
from run_adaptive_cosim import run_cosim_pair

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reconnection_study")


BASE_SCENARIO: Dict[str, Any] = {
    "scenario_name": "Datacenter_Fault_Reconnection",
    "backend": "synthetic",
    "sim_time_s": 3.5,
    "boundary_bus": "5385",
    "datacenter_rated_mw": 150.0,
    "datacenter_pf": 0.98,
    "component_profile": "datacenter_vfd",
    "trip_v_threshold": 0.70,
    "reconnect_time_s": 2.0,
    "reconnect_ramp_s": 0.40,
    "disturbance": {
        "type": "three_phase_fault",
        "t_start_s": 1.0,
        "t_clear_s": 1.0833,
        "fault_impedance_pu": 0.15,
    },
    "scheduler": {
        "mode": "learned_adaptive",
        "dt_min_s": 0.002,
        "dt_max_s": 0.050,
        "dt_init_s": 0.010,
        "surprise_tol_mw": 3.5,
        "uncertainty_tol": 0.18,
        "allow_surrogate_bypass": True,
    },
}


def run_single_case(case_name: str, reconnect_mode: str, backend: str = "synthetic") -> Dict[str, Any]:
    """Execute one reconnection case and capture timeseries."""
    scenario = copy.deepcopy(BASE_SCENARIO)
    scenario["scenario_name"] = f"Reconnection_{case_name}"
    scenario["reconnect_mode"] = reconnect_mode
    scenario["backend"] = backend

    log.info("=" * 70)
    log.info(f"STARTING RECONNECTION STUDY: {case_name.upper()} (mode={reconnect_mode})")
    log.info(f"Fault: {scenario['disturbance']['t_start_s']}s -> {scenario['disturbance']['t_clear_s']}s")
    log.info(f"Reconnection: t={scenario['reconnect_time_s']}s")
    log.info("=" * 70)

    out_file = SCRIPT_DIR / f"results_{reconnect_mode}.json"
    res = run_cosim_pair(
        scenario=scenario,
        core_type="inproc",
        results_path=str(out_file),
        simulate_delay=False,
    )
    return res


def plot_comparison(results_a: Dict[str, Any], results_b: Dict[str, Any], save_path: str = "reconnection_study_comparison.png"):
    """Generate 4-panel publication-grade comparison plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not installed -- skipping plot generation.")
        return

    hist_a = results_a.get("history", {})
    hist_b = results_b.get("history", {})

    t_a = np.array(hist_a.get("t_s", []))
    v_a = np.array(hist_a.get("v_mag_pu", []))
    p_a = np.array(hist_a.get("p_mw", []))
    q_a = np.array(hist_a.get("q_mvar", []))
    dt_a = np.array(hist_a.get("dt_s", [])) * 1e3
    f_a = np.array(hist_a.get("freq_hz", []))
    skip_a = np.array(hist_a.get("skip_emt", []), dtype=bool)

    t_b = np.array(hist_b.get("t_s", []))
    v_b = np.array(hist_b.get("v_mag_pu", []))
    p_b = np.array(hist_b.get("p_mw", []))
    q_b = np.array(hist_b.get("q_mvar", []))
    dt_b = np.array(hist_b.get("dt_s", [])) * 1e3
    f_b = np.array(hist_b.get("freq_hz", []))
    skip_b = np.array(hist_b.get("skip_emt", []), dtype=bool)

    fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True, dpi=150)
    plt.subplots_adjust(hspace=0.22)

    # Panel 1: Voltage
    axes[0].plot(t_a, v_a, "r-", label="Case A: Instantaneous Step", linewidth=1.7)
    axes[0].plot(t_b, v_b, "b-", label="Case B: Staged Soft Ramp", linewidth=1.7)
    axes[0].axvspan(1.0, 1.0833, color="gray", alpha=0.25, label="3Φ Fault (5-cycle)")
    axes[0].axvline(2.0, color="green", linestyle="--", alpha=0.7, label="Reconnection (t=2.0s)")
    axes[0].set_ylabel("PCC Voltage (pu)", fontweight="bold")
    axes[0].set_title("150 MW Datacenter Fault-Trip & Reconnection Study (Bus 5385, 161 kV)", fontsize=13, fontweight="bold")
    axes[0].grid(True, linestyle=":", alpha=0.6)
    axes[0].legend(loc="lower right", fontsize=8, ncol=2)

    # Panel 2: Datacenter Active & Reactive Power
    axes[1].plot(t_a, p_a, "r-", label="P (Case A Step)", linewidth=1.5)
    axes[1].plot(t_b, p_b, "b-", label="P (Case B Ramp)", linewidth=1.5)
    axes[1].plot(t_a, q_a, "r--", label="Q (Case A Step)", linewidth=1.2, alpha=0.7)
    axes[1].plot(t_b, q_b, "b--", label="Q (Case B Ramp)", linewidth=1.2, alpha=0.7)
    axes[1].set_ylabel("Datacenter P & Q (MW/MVAR)", fontweight="bold")
    axes[1].grid(True, linestyle=":", alpha=0.6)
    axes[1].legend(loc="center right", fontsize=8, ncol=2)

    # Panel 3: Grid Frequency
    axes[2].plot(t_a, f_a, "r-", label="Case A Frequency", linewidth=1.5)
    axes[2].plot(t_b, f_b, "b-", label="Case B Frequency", linewidth=1.5)
    axes[2].axhline(60.0, color="black", linestyle=":", alpha=0.5)
    axes[2].set_ylabel("Frequency (Hz)", fontweight="bold")
    axes[2].grid(True, linestyle=":", alpha=0.6)
    axes[2].legend(loc="lower left", fontsize=8)

    # Panel 4: Adaptive Co-Simulation Step Size & Bypass Status
    axes[3].plot(t_a, dt_a, "r-", label="Δt Step (Case A)", linewidth=1.3, alpha=0.85)
    axes[3].plot(t_b, dt_b, "b-", label="Δt Step (Case B)", linewidth=1.3, alpha=0.85)
    axes[3].set_ylabel("Co-Sim Δt (ms)", fontweight="bold")
    axes[3].set_xlabel("Time (seconds)", fontweight="bold")
    axes[3].grid(True, linestyle=":", alpha=0.6)
    axes[3].set_ylim(0, 55)
    axes[3].legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(save_path)
    log.info(f"Comparison plot saved successfully to: {save_path}")


def print_metrics_table(res_a: Dict[str, Any], res_b: Dict[str, Any]):
    """Print markdown-formatted summary metrics table."""
    hist_a = res_a.get("history", {})
    hist_b = res_b.get("history", {})

    t_a = np.array(hist_a.get("t_s", []))
    v_a = np.array(hist_a.get("v_mag_pu", []))
    f_a = np.array(hist_a.get("freq_hz", []))

    t_b = np.array(hist_b.get("t_s", []))
    v_b = np.array(hist_b.get("v_mag_pu", []))
    f_b = np.array(hist_b.get("freq_hz", []))

    # Reconnection window nadir (t >= 2.0s)
    mask_rec_a = t_a >= 1.99
    mask_rec_b = t_b >= 1.99

    v_rec_nadir_a = float(np.min(v_a[mask_rec_a])) if np.any(mask_rec_a) else 1.0
    v_rec_nadir_b = float(np.min(v_b[mask_rec_b])) if np.any(mask_rec_b) else 1.0

    f_nadir_a = float(np.min(f_a)) if len(f_a) else 60.0
    f_nadir_b = float(np.min(f_b)) if len(f_b) else 60.0

    steps_a = res_a.get("n_steps", 0)
    emt_a = res_a.get("pscad_stats", {}).get("emt_calls", 0)
    bypass_a = res_a.get("pscad_stats", {}).get("emt_skipped", 0)
    ratio_a = bypass_a / max(1, steps_a) * 100.0

    steps_b = res_b.get("n_steps", 0)
    emt_b = res_b.get("pscad_stats", {}).get("emt_calls", 0)
    bypass_b = res_b.get("pscad_stats", {}).get("emt_skipped", 0)
    ratio_b = bypass_b / max(1, steps_b) * 100.0

    print("\n" + "=" * 80)
    print("                    RECONNECTION STUDY RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'Metric':<36} | {'Case A (Instant Step)':<18} | {'Case B (Staged Ramp)':<18}")
    print("-" * 80)
    print(f"{'Fault Nadir Voltage (pu)':<36} | {np.min(v_a):<18.4f} | {np.min(v_b):<18.4f}")
    print(f"{'Reconnection Nadir Voltage (pu)':<36} | {v_rec_nadir_a:<18.4f} | {v_rec_nadir_b:<18.4f}")
    print(f"{'Reconnection Voltage Drop ΔV (pu)':<36} | {1.005 - v_rec_nadir_a:<18.4f} | {1.005 - v_rec_nadir_b:<18.4f}")
    print(f"{'Frequency Minimum (Hz)':<36} | {f_nadir_a:<18.4f} | {f_nadir_b:<18.4f}")
    print(f"{'Total Co-Sim Steps':<36} | {steps_a:<18} | {steps_b:<18}")
    print(f"{'EMT Evaluations Called':<36} | {emt_a:<18} | {emt_b:<18}")
    print(f"{'EMT Evaluations Bypassed':<36} | {bypass_a:<18} | {bypass_b:<18}")
    print(f"{'Surrogate Bypass Ratio':<36} | {ratio_a:<17.1f}% | {ratio_b:<17.1f}%")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="HELIOS Reconnection Study Benchmark")
    parser.add_argument("--backend", default="synthetic", choices=["synthetic", "psse"])
    parser.add_argument("--out-plot", default="reconnection_study_comparison.png")
    args = parser.parse_args()

    # Run Case A: Instantaneous Step Reconnection
    res_a = run_single_case("Case_A_Instant_Step", reconnect_mode="instantaneous", backend=args.backend)

    # Run Case B: Staged Soft-Start Ramp
    res_b = run_single_case("Case_B_Staged_Ramp", reconnect_mode="staged_ramp", backend=args.backend)

    # Print summary table
    print_metrics_table(res_a, res_b)

    # Generate comparison plot
    plot_comparison(res_a, res_b, save_path=str(SCRIPT_DIR / args.out_plot))


if __name__ == "__main__":
    main()
