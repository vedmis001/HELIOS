"""
run_reconnection_study.py
═══════════════════════════════════════════════════════════════════════════════
HELIOS Co-Simulation — Datacenter Fault-Trip & Reconnection Benchmark

Compares:
  1. HELIOS Co-Sim Instantaneous Reconnection (PSCAD EMT + PSS/E TS Step)
  2. HELIOS Co-Sim Staged Soft-Start Ramp (PSCAD EMT + PSS/E TS 400ms Ramp)
  3. No PSS/E TS Dynamics (PSCAD Standalone against a Stiff Grid / Infinite Bus)

Motivates why Co-Simulation is essential:
  - Without PSS/E TS (Stiff Grid): Completely misses bulk grid second-swing voltage
    sag, generator inertia extraction, and system-wide frequency nadir.
  - Without PSCAD EMT (Pure TS): Completely misses converter sub-cycle inrush
    surges (P ~ 188 MW, Q ~ 67 MVAR) and DC capacitor pre-charge dynamics.
  - With HELIOS Co-Sim: Accurately couples device-scale converter physics with
    wide-area transmission stability.
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
HELIOS_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DATA_DIR = HELIOS_ROOT / "results" / "data"
RESULTS_FIGURES_DIR = HELIOS_ROOT / "results" / "figures"
RESULTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

if str(HELIOS_ROOT) not in sys.path:
    sys.path.insert(0, str(HELIOS_ROOT))

import helics as h
from federates.emt.helios_pscad_federate import run_cosim as run_pscad_loop
from federates.ts.helios_ts_federate import run_ts_federate
from runners.run_adaptive_cosim import run_cosim_pair

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
        "fault_impedance_pu": 0.02,  # Bolted 3-phase fault pulling V < 0.20 pu
    },
    "scheduler": {
        "mode": "learned_adaptive",
        "dt_min_s": 0.002,
        "dt_max_s": 0.040,
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

    log.info("=" * 75)
    log.info(f"RUNNING CASE: {case_name.upper()} | Backend={backend} | Mode={reconnect_mode}")
    log.info(f"Fault: {scenario['disturbance']['t_start_s']}s -> {scenario['disturbance']['t_clear_s']}s (Zf={scenario['disturbance']['fault_impedance_pu']} pu)")
    log.info(f"Reconnection: t={scenario['reconnect_time_s']}s")
    log.info("=" * 75)

    out_file = RESULTS_DATA_DIR / f"results_{case_name.lower()}.json"
    res = run_cosim_pair(
        scenario=scenario,
        core_type="inproc",
        results_path=str(out_file),
        simulate_delay=False,
    )
    return res


def compute_adaptive_ylim(data, pad_ratio=0.10, force_zero_bottom=False, min_span=0.05):
    valid = data[np.isfinite(data)]
    if len(valid) == 0:
        return 0.0, 1.0
    d_min = float(np.min(valid))
    d_max = float(np.max(valid))
    span = max(d_max - d_min, min_span)
    y_min = d_min - span * pad_ratio
    y_max = d_max + span * pad_ratio
    if force_zero_bottom:
        y_min = max(0.0, y_min)
    return y_min, y_max


def plot_three_case_comparison(
    res_step: Dict[str, Any],
    res_ramp: Dict[str, Any],
    res_no_ts: Dict[str, Any],
    save_path: str = "helios_reconnection_comparison.png",
):
    """Generate high-clarity 2-column publication figure comparing the three cases."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MultipleLocator, FormatStrFormatter

    def get_arrays(res):
        hist = res.get("history", {})
        t = np.array(hist.get("t_s", []))
        v = np.array(hist.get("v_mag_pu", []))
        p = np.array(hist.get("p_mw", []))
        q = np.array(hist.get("q_mvar", []))
        f = np.array(hist.get("freq_hz", []))
        dt = np.array(hist.get("dt_s", [])) * 1e3
        skip = np.array(hist.get("skip_emt", []), dtype=bool)
        return t, v, p, q, f, dt, skip

    t_s, v_s, p_s, q_s, f_s, dt_s, skip_s = get_arrays(res_step)
    t_r, v_r, p_r, q_r, f_r, dt_r, skip_r = get_arrays(res_ramp)
    t_n, v_n, p_n, q_n, f_n, dt_n, skip_n = get_arrays(res_no_ts)

    fig, axes = plt.subplots(4, 2, figsize=(20, 15), dpi=220, gridspec_kw={"width_ratios": [1.35, 1.0]})
    plt.subplots_adjust(hspace=0.28, wspace=0.16, left=0.06, right=0.96, top=0.92, bottom=0.06)

    # Shading and gridlines
    for r in range(4):
        # Column 0: Full Overview (0 to 3.5s)
        axes[r, 0].xaxis.set_major_locator(MultipleLocator(0.2))
        axes[r, 0].xaxis.set_minor_locator(MultipleLocator(0.05))
        axes[r, 0].xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        axes[r, 0].grid(True, which="major", linestyle="-", color="#d3d3d3", alpha=0.75, linewidth=0.8)
        axes[r, 0].grid(True, which="minor", linestyle=":", color="#e8e8e8", alpha=0.45, linewidth=0.5)
        axes[r, 0].tick_params(axis="both", which="major", labelsize=10)

        # Column 1: Reconnection Detail Zoom (1.8s to 2.8s)
        axes[r, 1].set_xlim(1.8, 2.8)
        axes[r, 1].xaxis.set_major_locator(MultipleLocator(0.2))
        axes[r, 1].xaxis.set_minor_locator(MultipleLocator(0.05))
        axes[r, 1].xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        axes[r, 1].grid(True, which="major", linestyle="-", color="#d3d3d3", alpha=0.75, linewidth=0.8)
        axes[r, 1].grid(True, which="minor", linestyle=":", color="#e8e8e8", alpha=0.45, linewidth=0.5)
        axes[r, 1].tick_params(axis="both", which="major", labelsize=10)

        # Highlight events
        for c in range(2):
            axes[r, c].axvspan(1.0, 1.0833, color="#ff9896", alpha=0.28)
            axes[r, c].axvline(2.0, color="#2ca02c", linestyle="--", linewidth=1.5, alpha=0.8)

    # Labels and Legends
    label_step = "HELIOS Co-Sim: Instantaneous Step (EMT + TS)"
    label_ramp = "HELIOS Co-Sim: Staged Soft Ramp (EMT + TS)"
    label_nots = "No PSS/E TS: PSCAD Alone on Stiff Grid (No Bulk Dynamics)"

    # ── Row 0: PCC Voltage ────────────────────────────────────────────────────
    y0_min, y0_max = compute_adaptive_ylim(np.concatenate([v_s, v_r, v_n]), pad_ratio=0.08)
    for c, ax in enumerate([axes[0, 0], axes[0, 1]]):
        ax.plot(t_s, v_s, color="#d62728", linewidth=1.8, label=label_step)
        ax.plot(t_r, v_r, color="#2ca02c", linewidth=2.0, label=label_ramp)
        ax.plot(t_n, v_n, color="#1f77b4", linewidth=1.6, linestyle="--", label=label_nots)
        ax.set_ylabel("PCC Voltage (pu)", fontsize=11, fontweight="bold")
        ax.set_ylim(max(0.0, y0_min), min(1.20, y0_max))
        ax.yaxis.set_major_locator(MultipleLocator(0.2))
        if c == 0:
            ax.set_title("Full Simulation Overview (0 to 3.5s)", fontsize=13, fontweight="bold", pad=8)
            ax.legend(loc="lower right", fontsize=8.5, framealpha=0.92)
        else:
            ax.set_title("Reconnection Detail Zoom (1.8s to 2.8s)", fontsize=13, fontweight="bold", pad=8)

    # ── Row 1: Datacenter Active Power P ──────────────────────────────────────
    y1_min, y1_max = compute_adaptive_ylim(np.concatenate([p_s, p_r, p_n]), pad_ratio=0.10, force_zero_bottom=True)
    for c, ax in enumerate([axes[1, 0], axes[1, 1]]):
        ax.plot(t_s, p_s, color="#d62728", linewidth=1.8, label=label_step)
        ax.plot(t_r, p_r, color="#2ca02c", linewidth=2.0, label=label_ramp)
        ax.plot(t_n, p_n, color="#1f77b4", linewidth=1.6, linestyle="--", label=label_nots)
        ax.axhline(150.0, color="#8c564b", linestyle=":", linewidth=1.1, label="Nominal 150 MW")
        ax.set_ylabel("Active Power P (MW)", fontsize=11, fontweight="bold")
        ax.set_ylim(0.0, max(210.0, y1_max))
        ax.yaxis.set_major_locator(MultipleLocator(50.0))
        if c == 0:
            ax.legend(loc="center right", fontsize=8.5, framealpha=0.92)

    # ── Row 2: Datacenter Reactive Power Q ────────────────────────────────────
    y2_min, y2_max = compute_adaptive_ylim(np.concatenate([q_s, q_r, q_n]), pad_ratio=0.12, force_zero_bottom=True)
    for c, ax in enumerate([axes[2, 0], axes[2, 1]]):
        ax.plot(t_s, q_s, color="#d62728", linewidth=1.8, label=label_step)
        ax.plot(t_r, q_r, color="#2ca02c", linewidth=2.0, label=label_ramp)
        ax.plot(t_n, q_n, color="#1f77b4", linewidth=1.6, linestyle="--", label=label_nots)
        ax.axhline(30.6, color="#8c564b", linestyle=":", linewidth=1.1, label="Nominal 30.6 MVAR")
        ax.set_ylabel("Reactive Power Q (MVAR)", fontsize=11, fontweight="bold")
        ax.set_ylim(-2.0, max(85.0, y2_max))
        ax.yaxis.set_major_locator(MultipleLocator(20.0))
        if c == 0:
            ax.legend(loc="center right", fontsize=8.5, framealpha=0.92)

    # ── Row 3: Grid Frequency ─────────────────────────────────────────────────
    for c, ax in enumerate([axes[3, 0], axes[3, 1]]):
        ax.plot(t_s, f_s, color="#d62728", linewidth=1.8, label=label_step)
        ax.plot(t_r, f_r, color="#2ca02c", linewidth=2.0, label=label_ramp)
        ax.plot(t_n, f_n, color="#1f77b4", linewidth=1.6, linestyle="--", label=label_nots)
        ax.axhline(60.0, color="black", linestyle=":", linewidth=1.1)
        ax.set_ylabel("Frequency (Hz)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Simulation Time (seconds, major ticks every 0.2s)", fontsize=11, fontweight="bold")
        ax.set_ylim(59.60, 60.35)
        ax.yaxis.set_major_locator(MultipleLocator(0.2))
        if c == 0:
            ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92)

    fig.suptitle("HELIOS Co-Simulation Value Demonstration: 150 MW Datacenter Reconnection Study", fontsize=16, fontweight="bold", y=0.965)
    fig.savefig(save_path, bbox_inches="tight")
    log.info(f"High-clarity 3-case comparison plot saved to: {save_path}")


def print_comparison_table(res_step, res_ramp, res_nots):
    def get_stats(res):
        hist = res.get("history", {})
        t = np.array(hist.get("t_s", []))
        v = np.array(hist.get("v_mag_pu", []))
        p = np.array(hist.get("p_mw", []))
        q = np.array(hist.get("q_mvar", []))
        f = np.array(hist.get("freq_hz", []))

        # Reconnection window (t >= 1.99s)
        rec_mask = t >= 1.99
        v_rec_nadir = float(np.min(v[rec_mask])) if np.any(rec_mask) else 1.0
        p_inrush_peak = float(np.max(p[rec_mask])) if np.any(rec_mask) else 150.0
        q_inrush_peak = float(np.max(q[rec_mask])) if np.any(rec_mask) else 30.6
        f_min = float(np.min(f)) if len(f) else 60.0

        steps = res.get("total_steps") or len(hist.get("t_s", []))
        emt_calls = res.get("emt_sync_calls", 0)
        skipped = res.get("surrogate_bypasses", 0)
        bypass_pct = (skipped / max(1, steps)) * 100.0

        return {
            "v_rec_nadir": v_rec_nadir,
            "p_peak": p_inrush_peak,
            "q_peak": q_inrush_peak,
            "f_min": f_min,
            "steps": steps,
            "emt_calls": emt_calls,
            "bypass_pct": bypass_pct,
        }

    s_step = get_stats(res_step)
    s_ramp = get_stats(res_ramp)
    s_nots = get_stats(res_nots)

    print("\n" + "=" * 92)
    print("           HELIOS CO-SIMULATION RECONNECTION STUDY: THREE-WAY BENCHMARK")
    print("=" * 92)
    print(f"{'Metric':<34} | {'1. Co-Sim Step':<16} | {'2. Co-Sim Ramp':<16} | {'3. No PSS/E TS (Stiff)':<18}")
    print("-" * 92)
    print(f"{'Reconnection Voltage Nadir (pu)':<34} | {s_step['v_rec_nadir']:<16.4f} | {s_ramp['v_rec_nadir']:<16.4f} | {s_nots['v_rec_nadir']:<18.4f}")
    print(f"{'Secondary Voltage Drop ΔV (pu)':<34} | {1.005 - s_step['v_rec_nadir']:<16.4f} | {1.005 - s_ramp['v_rec_nadir']:<16.4f} | {1.005 - s_nots['v_rec_nadir']:<18.4f}")
    print(f"{'Peak Active Power Inrush (MW)':<34} | {s_step['p_peak']:<16.1f} | {s_ramp['p_peak']:<16.1f} | {s_nots['p_peak']:<18.1f}")
    print(f"{'Peak Reactive Inrush Surge (MVAR)':<34} | {s_step['q_peak']:<16.1f} | {s_ramp['q_peak']:<16.1f} | {s_nots['q_peak']:<18.1f}")
    print(f"{'System Frequency Minimum (Hz)':<34} | {s_step['f_min']:<16.4f} | {s_ramp['f_min']:<16.4f} | {s_nots['f_min']:<18.4f}")
    print(f"{'Total Co-Simulation Steps':<34} | {s_step['steps']:<16} | {s_ramp['steps']:<16} | {s_nots['steps']:<18}")
    print(f"{'Surrogate EMT Bypass Ratio':<34} | {s_step['bypass_pct']:<15.1f}% | {s_ramp['bypass_pct']:<15.1f}% | {'N/A (Stiff)':<18}")
    print("=" * 92 + "\n")


def main():
    parser = argparse.ArgumentParser(description="HELIOS 3-Way Reconnection Benchmark Runner")
    parser.add_argument("--out-plot", default="helios_reconnection_comparison.png")
    args = parser.parse_args()

    # 1. Run Case 1: HELIOS Co-Sim Instantaneous Reconnection (EMT + TS Step)
    res_step = run_single_case("CoSim_Instant_Step", reconnect_mode="instantaneous", backend="synthetic")

    # 2. Run Case 2: HELIOS Co-Sim Staged Soft-Start Ramp (EMT + TS Ramp)
    res_ramp = run_single_case("CoSim_Staged_Ramp", reconnect_mode="staged_ramp", backend="synthetic")

    # 3. Run Case 3: No PSS/E TS Dynamics (PSCAD Standalone on Stiff Grid)
    res_no_ts = run_single_case("No_TS_Stiff_Grid", reconnect_mode="instantaneous", backend="stiff")

    # Print summary metrics table
    print_comparison_table(res_step, res_ramp, res_no_ts)

    # Generate 2-column comparative publication figure
    plot_path = RESULTS_FIGURES_DIR / args.out_plot
    plot_three_case_comparison(res_step, res_ramp, res_no_ts, save_path=str(plot_path))


if __name__ == "__main__":
    main()
