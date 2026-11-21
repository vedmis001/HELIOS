"""
Precise slide figure generator tailored for the exact layout of Slides 12 and 13:

Slide 12 (results/slide1_llm_emt_interface.png):
  - Fits right beside the 'GRAIL EMT simulator' diagram (approx 3.7" wide x 3.6" tall).
  - Vertical stack:
      1. User prompt bubble (2 lines, quotes, no label).
      2. Downward arrow with 'agent handled'.
      3. Mini config dictionary card.
      4. Downward arrow.
      5. Mini EMT output plot (12 ms).

Slide 13 (results/slide2_llm_adaptive_stepping.png):
  - Directly replaces the right-hand panel of Slide 13 (approx 4.8" wide x 3.6" tall).
  - Clean layout:
      Top (~65%): Adaptive waveform with 1 disturbance (fault at t=5 ms),
                  red dots at Claude-chosen time points, legend placed at top/outside waveform.
      Bottom (~35%): Horizontal bar chart comparing NR Solves / Solver Effort
                     (Fixed vs Classical LTE vs Claude Agent).
"""

import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.circuit import Circuit, ELEMENT_REGISTRY
from core.simulator import Simulator
from core.adaptive import TimeStepSettings, ClaudeTimeStepAgent
from components.transformer import Transformer
from components.battery import Battery
from components.buckboost import BuckBoost
from components.machine import InductionMachine

ELEMENT_REGISTRY["transformer"] = Transformer
ELEMENT_REGISTRY["battery"] = Battery
ELEMENT_REGISTRY["buckboost"] = BuckBoost
ELEMENT_REGISTRY["machine"] = InductionMachine


def generate_slide12_figure(out_path: str = "results/slide1_llm_emt_interface.png") -> None:
    """
    Vertical stack for the right half of Slide 12:
    [ User Prompt ]
          ↓ (agent handled)
    [ Config dict ]
          ↓
    [ Mini EMT Plot ]
    """
    with open("configs/ups_slice_test.json") as f:
        ups_cfg = json.load(f)

    t_end = 0.012  # 12 ms
    ups_cfg["t_end"] = t_end
    ups_cfg["nodes"].append("v_ind_in")
    ups_cfg["elements"].append({"type": "resistor", "name": "R_esr", "nodes": ["vbatt_p", "v_ind_in"], "value": 0.35})
    for el in ups_cfg["elements"]:
        if el["type"] == "buckboost":
            el["nodes"] = ["vdc_p", "vdc_n", "v_ind_in", "vbatt_n"]
            el["value"] = {"Ltot": 0.0005, "mode": "boost", "VH_ref": 900.0, "Kp_boost": 0.002, "Ti_boost": 0.004, "Dmax_boost": 0.45}
        elif el["type"] == "capacitor":
            el["value"] = 0.0015
        elif el["name"] == "R_compute_load":
            el["value"] = 4.0

    sim = Simulator(Circuit.from_config(ups_cfg), ups_cfg["dt"], t_end, mode="fixed")
    sim.run("fixed")
    t_ms = sim.time * 1e3
    vdc = sim.voltage("vdc_p") - sim.voltage("vdc_n")
    vbatt = sim.voltage("vbatt_p") - sim.voltage("vbatt_n")

    # Dimensions: 3.6 inches wide by 4.2 inches tall (fits cleanly in Slide 12 blank right space)
    fig = plt.figure(figsize=(3.6, 4.2), dpi=300)
    gs = fig.add_gridspec(3, 1, height_ratios=[0.72, 1.05, 1.25], hspace=0.44)

    # 1. User prompt (2 lines, no header label, dark rounded card)
    ax_prompt = fig.add_subplot(gs[0])
    ax_prompt.set_axis_off()
    ax_prompt.set_xlim(0, 1)
    ax_prompt.set_ylim(0, 1)

    card_prompt = FancyBboxPatch(
        (0.01, 0.05), 0.98, 0.90,
        boxstyle="round,pad=0.03,rounding_size=0.06",
        fc="#1e222a", ec="#4c566a", lw=1.0
    )
    ax_prompt.add_patch(card_prompt)
    prompt_text = (
        "\"Simulate the 600V UPS battery and boost\n"
        "converter regulating to 900V DC for 12 ms.\""
    )
    ax_prompt.text(
        0.50, 0.50, prompt_text,
        color="#eceff4", fontsize=7.2, style="italic", linespacing=1.35,
        ha="center", va="center", family="sans-serif"
    )

    # Downward arrow 1 with "agent handled" placed in clean gap
    fig.text(
        0.50, 0.748, "↓  (agent handled)",
        fontsize=7.2, fontweight="bold", color="#2563eb", ha="center", va="center"
    )

    # 2. Config dict (compact code card)
    ax_cfg = fig.add_subplot(gs[1])
    ax_cfg.set_axis_off()
    ax_cfg.set_xlim(0, 1)
    ax_cfg.set_ylim(0, 1)

    card_cfg = FancyBboxPatch(
        (0.01, 0.02), 0.98, 0.96,
        boxstyle="round,pad=0.03,rounding_size=0.06",
        fc="#f8fafc", ec="#cbd5e1", lw=1.0
    )
    ax_cfg.add_patch(card_cfg)
    cfg_text = (
        "config = {\n"
        "  \"dt\": 1e-5, \"t_end\": 0.012,\n"
        "  \"elements\": [\n"
        "    {\"type\": \"battery\",   \"Vnom\": 600},\n"
        "    {\"type\": \"buckboost\", \"VH_ref\": 900},\n"
        "    {\"type\": \"capacitor\", \"C\": 1.5e-3}\n"
        "  ]\n"
        "}"
    )
    ax_cfg.text(
        0.06, 0.08, cfg_text,
        color="#0f172a", fontsize=6.6, family="monospace", linespacing=1.18
    )

    # Downward arrow 2 with text placed in spacious gap
    fig.text(
        0.50, 0.405, "↓  (Sparse MNA solve)",
        fontsize=7.2, fontweight="bold", color="#2563eb", ha="center", va="center"
    )

    # 3. Mini EMT plot
    ax_plot = fig.add_subplot(gs[2])
    ax_plot.axhline(900.0, color="#9ca3af", ls=":", lw=0.9, label="900 V Ref")
    ax_plot.plot(t_ms, vdc, color="#dc2626", lw=1.6, label="$V_{dc}$")
    ax_plot.plot(t_ms, vbatt, color="#2563eb", lw=1.5, label="$V_{batt}$")
    ax_plot.set_xlim(0, 12)
    ax_plot.set_ylim(0, 1050)
    ax_plot.set_xlabel("Time (ms)", fontsize=7.2, labelpad=1)
    ax_plot.set_ylabel("Voltage (V)", fontsize=7.2, labelpad=1)
    ax_plot.tick_params(labelsize=6.8, pad=1)
    ax_plot.grid(True, alpha=0.3, linestyle="--")
    ax_plot.legend(loc="lower right", fontsize=6.6, frameon=True, framealpha=0.9, borderpad=0.3)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.subplots_adjust(left=0.17, right=0.96, top=0.96, bottom=0.10)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved Slide 12 figure to {out_path}")


def generate_slide13_figure(out_path: str = "results/slide2_llm_adaptive_stepping.png") -> None:
    """
    Direct replacement for the right panel on Slide 13:
      - Top (~68%): Waveform with single disturbance (fault at t=5 ms),
        red dots at Claude-chosen time steps, legend placed at the top (not covering waveform).
      - Bottom (~32%): Horizontal bar chart comparing NR Solves / Solver Effort.
    """
    def v_pulsed(t: float) -> float:
        return 10.0 if t <= 5e-3 else -5.0

    cfg = {
        "nodes": ["gnd", "n1", "n2", "n3"],
        "elements": [
            {"type": "vsource", "name": "Vs", "nodes": ["n1", "gnd"], "value": v_pulsed},
            {"type": "resistor", "name": "R1", "nodes": ["n1", "n2"], "value": 12.0},
            {"type": "inductor", "name": "L1", "nodes": ["n2", "n3"], "value": 4e-3},
            {"type": "capacitor", "name": "C1", "nodes": ["n3", "gnd"], "value": 25e-6},
        ],
    }
    event_times = np.array([5e-3])
    dt_base = 5e-6
    t_end = 0.012  # 12 ms

    sim_fixed = Simulator(Circuit.from_config(cfg), dt_base, t_end, mode="fixed")
    st_fixed = sim_fixed.run("fixed")

    settings = TimeStepSettings(
        tol_lte=2.5e-3,
        dt_min=2e-6,
        dt_max=4e-4,
        dt_normal=4e-5,
        dt_event=5e-6,
        t_event_window=8e-4,
        beta=0.8,
        event_times=event_times,
    )

    sim_pscad = Simulator(Circuit.from_config(cfg), dt_base, t_end, mode="pscad", settings=settings)
    st_pscad = sim_pscad.run_adaptive(mode="pscad", settings=settings, event_times=event_times)

    agent = ClaudeTimeStepAgent()
    # Run 1: initial baseline exploration
    sim_init = Simulator(Circuit.from_config(cfg), dt_base, t_end, mode="claude", settings=settings, agent=agent)
    sim_init.run_adaptive(mode="claude", settings=settings, event_times=event_times, agent=agent)

    # Feedback learning: analyze trajectory, identifying quiet settled interval (8-12 ms)
    agent.learn_from_run(sim_init, voltage_settle_band=0.03)

    # Run 2: learned execution taking 1-2 big steps across settled quiet periods
    sim_claude = Simulator(Circuit.from_config(cfg), dt_base, t_end, mode="claude", settings=settings, agent=agent)
    st_claude = sim_claude.run_adaptive(mode="claude", settings=settings, event_times=event_times, agent=agent)

    v_ref = sim_fixed.voltage("n3")

    # Dimensions: 4.8" wide x 3.6" tall (exact proportion of Slide 13 right panel)
    fig = plt.figure(figsize=(4.8, 3.6), dpi=300)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.75, 1.0], hspace=0.38)

    # --- Top: Waveform with Claude-chosen dots ---
    ax_wave = fig.add_subplot(gs[0])
    ax_wave.plot(
        sim_fixed.time * 1e3, v_ref,
        color="#4b5563", lw=1.2, alpha=0.9,
        label="Exact Waveform (Fixed $\\Delta t$)"
    )
    ax_wave.plot(
        sim_claude.time * 1e3, sim_claude.voltage("n3"),
        "o", color="#dc2626", markersize=3.2, markeredgecolor="white", markeredgewidth=0.3,
        label=f"Claude-chosen $\\Delta t$ ({st_claude['n_accepted_steps']} steps)"
    )

    # Disturbance marker
    ax_wave.axvline(5.0, color="#2563eb", ls="--", lw=1.0, alpha=0.85)
    ax_wave.text(5.15, 13.5, "disturbance", fontsize=6.8, fontweight="bold", color="#1d4ed8")

    # Annotations placed with short, clear arrows pointing directly at their target features
    # 1. Large dt arrow: short, pointing directly DOWN onto the wide-spaced dots on the flat plateau (t = 3.6 ms)
    ax_wave.annotate(
        "large $\\Delta t$\n(quiet)",
        xy=(3.6, 10.3), xytext=(3.6, 13.6),
        fontsize=6.8, color="#059669", fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color="#059669", lw=0.9),
    )

    # 2. Small dt arrow: short, pointing directly at the dense dot cluster on the steep disturbance slope (t = 5.6 ms)
    ax_wave.annotate(
        "small $\\Delta t$\n(transient)",
        xy=(5.5, -1.0), xytext=(3.2, -3.0),
        fontsize=6.8, color="#dc2626", fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color="#dc2626", lw=0.9),
    )

    # 3. Learned big-step leap arrow: pointing down onto the wide-spaced 2-step tail in 8-12 ms
    ax_wave.annotate(
        "learned 2-step\nleap (quiet)",
        xy=(10.17, -4.8), xytext=(10.17, -0.6),
        fontsize=6.8, color="#7c3aed", fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color="#7c3aed", lw=0.9),
    )

    ax_wave.set_title("Claude-Directed Adaptive Time Stepping", fontsize=8.2, fontweight="bold", pad=4)
    ax_wave.set_xlabel("Time (ms)", fontsize=7.2, labelpad=1)
    ax_wave.set_ylabel("Voltage (V)", fontsize=7.2, labelpad=1)
    ax_wave.set_xlim(0, 12)
    ax_wave.set_ylim(-10, 17)
    ax_wave.tick_params(labelsize=6.8, pad=1)
    ax_wave.grid(True, alpha=0.3, linestyle="--")
    # Legend placed slightly lower on the right so it doesn't block the disturbance marker
    ax_wave.legend(bbox_to_anchor=(0.99, 0.76), loc="upper right", fontsize=6.4, frameon=True, framealpha=0.9, borderpad=0.25)

    # --- Bottom: Horizontal Bar Chart of Solves / Effort ---
    ax_bar = fig.add_subplot(gs[1])
    modes = ["Claude (Learned)", "Classical LTE", "Fixed (Base)"]
    solves = [st_claude["total_solves"], st_pscad["total_solves"], st_fixed["total_solves"]]
    colors = ["#dc2626", "#3b82f6", "#6b7280"]

    y_pos = np.arange(len(modes))
    bars = ax_bar.barh(y_pos, solves, color=colors, height=0.55, edgecolor="#1f2937", lw=0.5)
    ax_bar.set_xscale("log")
    ax_bar.set_xlim(30, 8000)
    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(modes, fontsize=7.0, fontweight="bold")
    ax_bar.set_xlabel("Total MNA / Newton Solves (log scale)", fontsize=7.2, labelpad=1)
    ax_bar.set_title("Solver Effort & Speedup", fontsize=8.0, fontweight="bold", pad=3)
    ax_bar.tick_params(labelsize=6.8, pad=1)
    ax_bar.grid(True, axis="x", alpha=0.3, linestyle="--")

    for bar, s_val in zip(bars, solves):
        speedup = st_fixed["total_solves"] / s_val
        txt = f" {s_val:,} ({speedup:.1f}x)" if speedup > 1.1 else f" {s_val:,} (1.0x)"
        ax_bar.text(
            s_val * 1.15,
            bar.get_y() + bar.get_height() / 2.0,
            txt,
            va="center", ha="left", fontsize=6.8, fontweight="bold", color="#111827"
        )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.subplots_adjust(left=0.22, right=0.96, top=0.92, bottom=0.13)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved Slide 13 figure to {out_path}")


if __name__ == "__main__":
    generate_slide12_figure()
    generate_slide13_figure()
