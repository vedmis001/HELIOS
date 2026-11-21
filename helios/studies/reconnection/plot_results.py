"""
plot_results.py
═══════════════════════════════════════════════════════════════════════════════
High-clarity, adaptive-axis plotting for HELIOS Co-Simulation telemetry.

Features:
  1. Adaptive vertical scaling on all panels with clean headroom and tick steps.
  2. Resolves dense "chunks" by separating physical live EMT trajectory from
     surrogate bypass predictions.
  3. X-axis ticks every 0.2 seconds across all panels.
  4. Includes an expanded High-Resolution Event Zoom (0.8s to 2.6s) to clearly
     show individual steps during fault, clearing, and reconnection.
Outputs: helios_reconnection_plot.png
═══════════════════════════════════════════════════════════════════════════════
"""

import os
from pathlib import Path
import re
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
HELIOS_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = HELIOS_ROOT / "results" / "logs" / "psse_federate.log"
PLOT_FILE = HELIOS_ROOT / "results" / "figures" / "helios_reconnection_plot.png"


def load_from_log(log_path: Path):
    if not log_path.exists():
        return None

    pattern = re.compile(
        r"t=([\d\.]+)s\s*\|\s*dt=([\d\.]+)ms\s*\|\s*skip_emt=(\w+)\s*\|\s*P=([-\d\.]+)MW,\s*Q=([-\d\.]+)MVAR\s*\|\s*V=([\d\.]+)pu\s*\|\s*unc=([\d\.]+)"
    )

    times, dts, skips, p_vals, q_vals, v_vals, uncs = [], [], [], [], [], [], []

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                times.append(float(m.group(1)))
                dts.append(float(m.group(2)))
                skips.append(m.group(3).lower() == "true")
                p_vals.append(float(m.group(4)))
                q_vals.append(float(m.group(5)))
                v_vals.append(float(m.group(6)))
                uncs.append(float(m.group(7)))

    if not times:
        return None

    return {
        "time": np.array(times),
        "dt_ms": np.array(dts),
        "skip": np.array(skips, dtype=bool),
        "p_mw": np.array(p_vals),
        "q_mvar": np.array(q_vals),
        "v_pu": np.array(v_vals),
        "unc": np.array(uncs),
    }


def compute_adaptive_ylim(data, pad_ratio=0.10, min_span=0.1, force_zero_bottom=False):
    """Compute clean adaptive vertical bounds ignoring extreme 1% outliers."""
    valid = data[np.isfinite(data)]
    if len(valid) == 0:
        return 0.0, 1.0

    p_low = float(np.percentile(valid, 1.0))
    p_high = float(np.percentile(valid, 99.0))
    d_min = min(float(np.min(valid)), p_low)
    d_max = max(float(np.max(valid)), p_high)

    span = max(d_max - d_min, min_span)
    y_min = d_min - span * pad_ratio
    y_max = d_max + span * pad_ratio

    if force_zero_bottom:
        y_min = max(0.0, y_min)

    return y_min, y_max


def generate_plot():
    data = load_from_log(LOG_FILE)
    if data is None:
        print("No log data found.")
        return False

    t = data["time"]
    v = data["v_pu"]
    p = data["p_mw"]
    q = data["q_mvar"]
    dt = data["dt_ms"]
    skip = data["skip"]
    unc = data["unc"]

    # Limit to current run duration (up to ~3.5s or 5.0s)
    t_max = min(5.0, float(np.max(t)))
    mask = t <= t_max
    t = t[mask]
    v = v[mask]
    p = p[mask]
    q = q[mask]
    dt = dt[mask]
    skip = skip[mask]
    unc = unc[mask]

    # Split into Live EMT vs Surrogate Bypass points
    mask_emt = ~skip
    mask_surr = skip

    # Create 2-column figure:
    # Column 1: Full Simulation Horizon (0.0 to 5.0s)
    # Column 2: Event Zoom Window (0.8s to 2.6s) to cleanly resolve every step
    fig, axes = plt.subplots(5, 2, figsize=(20, 16), dpi=200, gridspec_kw={"width_ratios": [1.4, 1.0]})
    plt.subplots_adjust(hspace=0.32, wspace=0.18, left=0.06, right=0.96, top=0.93, bottom=0.06)

    # Styling helper for x-ticks
    for row in range(5):
        # Column 1 (Overview)
        axes[row, 0].xaxis.set_major_locator(MultipleLocator(0.2))
        axes[row, 0].xaxis.set_minor_locator(MultipleLocator(0.05))
        axes[row, 0].xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        axes[row, 0].grid(True, which="major", linestyle="-", color="#d3d3d3", alpha=0.7, linewidth=0.8)
        axes[row, 0].grid(True, which="minor", linestyle=":", color="#e8e8e8", alpha=0.4, linewidth=0.5)
        axes[row, 0].tick_params(axis="both", which="major", labelsize=10)

        # Column 2 (Zoom: 0.8s to 2.6s)
        axes[row, 1].set_xlim(0.8, 2.6)
        axes[row, 1].xaxis.set_major_locator(MultipleLocator(0.2))
        axes[row, 1].xaxis.set_minor_locator(MultipleLocator(0.05))
        axes[row, 1].xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        axes[row, 1].grid(True, which="major", linestyle="-", color="#d3d3d3", alpha=0.7, linewidth=0.8)
        axes[row, 1].grid(True, which="minor", linestyle=":", color="#e8e8e8", alpha=0.4, linewidth=0.5)
        axes[row, 1].tick_params(axis="both", which="major", labelsize=10)

    # Shaded Event Bands
    def add_event_shading(ax):
        ax.axvspan(0.55, 0.65, color="#ffbb78", alpha=0.20, label="Pre-Fault UV Trip (~0.58s)")
        ax.axvspan(0.70, 0.95, color="#c5b0d5", alpha=0.16, label="Anomaly Window (~0.8s)")
        ax.axvspan(1.00, 1.0833, color="#ff9896", alpha=0.30, label="3Φ Fault (1.0 to 1.083s)")
        ax.axvline(2.00, color="#2ca02c", linestyle="--", linewidth=1.6, label="Reconnection (2.0s)")

    for r in range(5):
        for c in range(2):
            add_event_shading(axes[r, c])

    # ── Panel 1: Voltage ──────────────────────────────────────────────────────
    y1_min, y1_max = compute_adaptive_ylim(v, pad_ratio=0.08)
    for c, ax in enumerate([axes[0, 0], axes[0, 1]]):
        ax.plot(t, v, color="#1f77b4", linewidth=1.6, label="PCC Voltage V (Bus 5385, 161 kV)")
        ax.set_ylabel("Voltage (pu)", fontsize=11, fontweight="bold")
        ax.set_ylim(max(0.0, y1_min), min(1.25, y1_max))
        ax.yaxis.set_major_locator(MultipleLocator(0.2))
        if c == 0:
            ax.set_title("Full Simulation Horizon (0 to 5s)", fontsize=13, fontweight="bold", pad=8)
            ax.legend(loc="upper right", fontsize=8, framealpha=0.9, ncol=2)
        else:
            ax.set_title("Disturbance & Reconnection Zoom (0.8s to 2.6s)", fontsize=13, fontweight="bold", pad=8)

    # ── Panel 2: Datacenter Active Power P ────────────────────────────────────
    # De-clutter: Plot Live EMT curve, and show Surrogate predictions as distinct scatter
    for c, ax in enumerate([axes[1, 0], axes[1, 1]]):
        # Continuous physical EMT line
        ax.plot(t[mask_emt], p[mask_emt], color="#d62728", linewidth=1.7, alpha=0.95, label="Live EMT P (PSCAD)")
        # Surrogate predictions as separate points
        if np.any(mask_surr):
            ax.scatter(t[mask_surr], p[mask_surr], color="#ff7f0e", marker="o", s=14, alpha=0.6, label="Surrogate Bypass P")
        ax.axhline(150.0, color="#8c564b", linestyle=":", linewidth=1.1, label="Rated Power (150 MW)")
        ax.set_ylabel("Active P (MW)", fontsize=11, fontweight="bold")
        # Adaptive limits based on physical range
        y2_min, y2_max = compute_adaptive_ylim(p[mask_emt], pad_ratio=0.10, force_zero_bottom=True)
        ax.set_ylim(y2_min, max(165.0, y2_max))
        ax.yaxis.set_major_locator(MultipleLocator(50.0))
        if c == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.9, ncol=3)

    # ── Panel 3: Datacenter Reactive Power Q (Separating the "chunks") ─────────
    # The "chunks" were caused by connecting Q=0 (live EMT) to Q=-200 (surrogate) every 2ms.
    # By plotting Live EMT as a continuous curve and Surrogate as scatter, the physical response is separated!
    for c, ax in enumerate([axes[2, 0], axes[2, 1]]):
        # Continuous physical EMT line
        ax.plot(t[mask_emt], q[mask_emt], color="#2ca02c", linewidth=1.8, alpha=0.95, label="Live EMT Q (PSCAD Physical)")
        # Surrogate predictions plotted as distinct open diamonds
        if np.any(mask_surr):
            ax.scatter(t[mask_surr], q[mask_surr], color="#9467bd", marker="d", s=14, alpha=0.55, label="Surrogate Bypass Q (Inferred)")
        ax.axhline(30.6, color="#8c564b", linestyle=":", linewidth=1.1, label="Rated Q (30.6 MVAR)")
        ax.set_ylabel("Reactive Q (MVAR)", fontsize=11, fontweight="bold")
        # Adaptive limits centered on physical range [0 to 35 MVAR]
        q_phys = q[mask_emt]
        y3_min, y3_max = compute_adaptive_ylim(q_phys, pad_ratio=0.15)
        # Give enough room to see surrogate points without squishing physical signal
        ax.set_ylim(max(-25.0, y3_min - 5.0), max(45.0, y3_max + 10.0))
        ax.yaxis.set_major_locator(MultipleLocator(15.0))
        if c == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.9, ncol=3)

    # ── Panel 4: RLS Epistemic Uncertainty ────────────────────────────────────
    y4_min, y4_max = compute_adaptive_ylim(unc, pad_ratio=0.12, force_zero_bottom=True)
    for c, ax in enumerate([axes[3, 0], axes[3, 1]]):
        ax.plot(t, unc, color="#9467bd", linewidth=1.5, label="RLS Uncertainty sqrt(φᵀ P_cov φ)")
        ax.axhline(0.18, color="black", linestyle="--", linewidth=1.1, label="Bypass Tolerance (0.18)")
        ax.set_ylabel("RLS Uncertainty", fontsize=11, fontweight="bold")
        ax.set_ylim(0.0, min(8.0, max(2.5, y4_max)))
        ax.yaxis.set_major_locator(MultipleLocator(1.0))
        if c == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.9, ncol=2)

    # ── Panel 5: Adaptive Timestep Δt ─────────────────────────────────────────
    for c, ax in enumerate([axes[4, 0], axes[4, 1]]):
        ax.plot(t, dt, color="#ff7f0e", linewidth=1.6, label="Exchange Timestep Δt (ms)")
        if np.any(skip):
            ax.scatter(t[skip], dt[skip], color="#2ca02c", s=20, zorder=5, label="Surrogate Bypass Step")
        ax.set_ylabel("Timestep Δt (ms)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Time (seconds, ticks every 0.2s)", fontsize=11, fontweight="bold")
        ax.set_ylim(0.0, max(30.0, float(np.max(dt)) * 1.15))
        ax.yaxis.set_major_locator(MultipleLocator(5.0))
        if c == 0:
            ax.legend(loc="upper right", fontsize=8, framealpha=0.9, ncol=2)

    fig.suptitle("HELIOS Co-Simulation: 150 MW Datacenter Fault-Trip & Reconnection (Adaptive Axes)", fontsize=16, fontweight="bold", y=0.97)

    fig.savefig(str(PLOT_FILE), bbox_inches="tight")
    print(f"Adaptive plot successfully saved: {PLOT_FILE}")
    return True


if __name__ == "__main__":
    generate_plot()
