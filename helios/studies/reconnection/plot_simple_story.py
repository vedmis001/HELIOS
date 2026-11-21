"""
plot_simple_story.py
═══════════════════════════════════════════════════════════════════════════════
Generates a clean, single-simulation, zero-legend 3-panel figure for presentations:
  - Panel 1: Grid PCC Voltage (pu)           [Transmission / PSS/E side]
  - Panel 2: Grid Frequency (Hz)             [Transmission / PSS/E side]
  - Panel 3: Internal UPS Battery Power (MW) [Datacenter / PSCAD side]

Reads existing results_cosim_staged_ramp.json and saves to:
  helios/results/figures/helios_simple_cosim_story.png
(Does NOT overwrite helios_reconnection_comparison.png)
═══════════════════════════════════════════════════════════════════════════════
"""

import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

HELIOS_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = HELIOS_ROOT / "results" / "data" / "results_cosim_staged_ramp.json"
OUT_FILE = HELIOS_ROOT / "results" / "figures" / "helios_simple_cosim_story.png"


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        res = json.load(f)

    hist = res["history"]
    t = np.array(hist["t_s"])
    v = np.array(hist["v_mag_pu"])
    freq = np.array(hist["freq_hz"])
    p_ups = np.array(hist["p_ups_mw"])

    fig, (ax_v, ax_f, ax_u) = plt.subplots(
        3, 1, sharex=True, figsize=(11.5, 9.2), dpi=240,
        gridspec_kw={"height_ratios": [1.05, 0.95, 1.2]}
    )
    plt.subplots_adjust(hspace=0.16, left=0.10, right=0.96, top=0.90, bottom=0.08)

    for ax in (ax_v, ax_f, ax_u):
        ax.set_xlim(0.0, 3.5)
        ax.xaxis.set_major_locator(MultipleLocator(0.5))
        ax.xaxis.set_minor_locator(MultipleLocator(0.1))
        ax.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        ax.grid(True, which="major", linestyle="-", color="#dcdcdc", alpha=0.8, linewidth=0.8)
        ax.grid(True, which="minor", linestyle=":", color="#ececec", alpha=0.5, linewidth=0.5)
        ax.tick_params(axis="both", which="major", labelsize=10.5)
        # Fault shading & reconnection marker
        ax.axvspan(1.0, 1.0833, color="#ff9896", alpha=0.30)
        ax.axvline(2.0, color="#2ca02c", linestyle="--", linewidth=1.6, alpha=0.85)

    # ── Panel 1: Grid Side (PCC Voltage) — unclipped full range ───────────────
    v_top = max(1.65, float(np.max(v)) + 0.14)
    ax_v.plot(t, v, color="#1f4e79", linewidth=2.3)
    ax_v.axhline(1.0, color="#888888", linestyle=":", linewidth=1.0, alpha=0.7)
    ax_v.set_ylabel("Grid PCC Voltage\n(pu)", fontsize=11.5, fontweight="bold", color="#1f4e79")
    ax_v.set_ylim(0.0, v_top)
    ax_v.yaxis.set_major_locator(MultipleLocator(0.3))
    ax_v.annotate(
        "Grid 3-Phase Fault\n(Voltage Collapse)",
        xy=(1.04, 0.17), xytext=(0.30, 0.38),
        arrowprops=dict(arrowstyle="->", color="#b22222", lw=1.4),
        fontsize=10, fontweight="bold", color="#b22222",
    )
    ax_v.annotate(
        "Post-Clearing\nRecovery Spike",
        xy=(1.10, float(np.max(v))), xytext=(1.35, v_top - 0.30),
        arrowprops=dict(arrowstyle="->", color="#1f4e79", lw=1.3),
        fontsize=9.5, fontweight="bold", color="#1f4e79",
    )
    ax_v.text(
        2.05, 0.42, "Grid Reconnection\n(t = 2.0 s)",
        fontsize=10, fontweight="bold", color="#1b6e1b",
    )

    # ── Panel 2: Grid Side (Frequency) ────────────────────────────────────────
    f_min = float(np.min(freq))
    f_max = float(np.max(freq))
    ax_f.axhline(60.0, color="#666666", linestyle=":", linewidth=1.1)
    ax_f.plot(t, freq, color="#7b2cbf", linewidth=2.3)
    ax_f.set_ylabel("Grid Frequency\n(Hz)", fontsize=11.5, fontweight="bold", color="#5a189a")
    ax_f.set_ylim(min(59.85, f_min - 0.08), max(60.58, f_max + 0.10))
    ax_f.yaxis.set_major_locator(MultipleLocator(0.2))
    ax_f.annotate(
        "150 MW Load Shed\n→ Grid Speeds Up",
        xy=(1.55, float(np.interp(1.55, t, freq))), xytext=(0.32, 60.34),
        arrowprops=dict(arrowstyle="->", color="#5a189a", lw=1.3),
        fontsize=10, fontweight="bold", color="#5a189a",
    )
    ax_f.annotate(
        "Smooth Return to 60 Hz\nDuring Soft Walk-In",
        xy=(2.70, float(np.interp(2.70, t, freq))), xytext=(2.58, 60.34),
        arrowprops=dict(arrowstyle="->", color="#5a189a", lw=1.3),
        fontsize=10, fontweight="bold", color="#5a189a",
    )

    # ── Panel 3: Datacenter Side (Internal UPS Power) ─────────────────────────
    ax_u.axhspan(0.0, 145.0, color="#fff3cd", alpha=0.25)
    ax_u.axhspan(-30.0, 0.0, color="#d1ecf1", alpha=0.30)
    ax_u.axhline(0.0, color="black", linestyle="-", linewidth=0.9, alpha=0.7)
    ax_u.plot(t, p_ups, color="#2ca02c", linewidth=2.5)
    ax_u.set_ylabel("Datacenter UPS Power\n(MW, +Discharge / -Charge)", fontsize=11.5, fontweight="bold", color="#1b6e1b")
    ax_u.set_xlabel("Simulation Time (seconds)", fontsize=11.5, fontweight="bold")
    ax_u.set_ylim(-26.0, 142.0)
    ax_u.yaxis.set_major_locator(MultipleLocator(30.0))

    ax_u.text(
        1.52, 126.5, "UPS Carries 120 MW Critical IT Load",
        ha="center", fontsize=10, fontweight="bold", color="#7a5200",
    )
    ax_u.annotate(
        "Controlled Soft Walk-In\n(400 ms Handoff to Grid)",
        xy=(2.20, 60.0), xytext=(2.48, 86.0),
        arrowprops=dict(arrowstyle="->", color="#1b6e1b", lw=1.4),
        fontsize=10, fontweight="bold", color="#1b6e1b",
    )
    ax_u.annotate(
        "Deferred Battery Recharge",
        xy=(2.85, -8.0), xytext=(2.50, -22.5),
        arrowprops=dict(arrowstyle="->", color="#0c5460", lw=1.3),
        fontsize=9.5, fontweight="bold", color="#0c5460",
    )

    fig.suptitle(
        "Coupled Grid–Datacenter Co-Simulation: Fault Ride-Through & Soft Reconnection",
        fontsize=14.5, fontweight="bold", y=0.955,
    )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FILE, bbox_inches="tight")
    print(f"Saved clean 3-panel plot to: {OUT_FILE}")


if __name__ == "__main__":
    main()
