#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════
  IRE Calibration Tool — Analysis
═══════════════════════════════════════════════════════════

Reads CSV files produced by calibrate.py and outputs:

  distance  — fits the RSSI→distance model, prints exact values
              to paste into backend/app/core/config.py

  survey    — loads the position survey, prints per-point errors
              and an ASCII heatmap of the room

Usage:
  pip install numpy scipy matplotlib

  python analyse.py distance          # fits all distance_*.csv files
  python analyse.py survey            # loads the most recent survey_*.csv
  python analyse.py survey --plot     # also shows matplotlib scatter plot

  python analyse.py distance --file data/distance_esp32_A_*.csv
"""

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


# ── Shared helpers ──────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def latest(pattern: str) -> Path | None:
    files = sorted(DATA_DIR.glob(pattern))
    return files[-1] if files else None


# ── Distance analysis ───────────────────────────────────────────────────────

def analyse_distance(files: list[Path]):
    """
    Fit a two-segment RSSI→distance model from calibration data.

    Segment 1 (near, d ≤ 1 m):  linear  rssi = rssi_1m + near_slope * (d - 1)
    Segment 2 (far,  d > 1 m):  linear  rssi = rssi_1m - far_dbm_per_m * (d - 1)

    From the two fits we derive:
      BLE_TX_POWER         = rssi_1m  (signal at 1 m reference)
      BLE_NEAR_RSSI        = rssi_1m  (boundary between segments)
      BLE_NEAR_DIST_AT_REF = d at which rssi = -50 dBm  (extrapolated)
      BLE_FAR_DBM_PER_M    = far-field slope in dBm / m
    """
    try:
        import numpy as np
        from scipy.stats import linregress
    except ImportError:
        print("  ✗  numpy and scipy are required:  pip install numpy scipy")
        return

    # Collect all rows grouped by (gateway, distance)
    # { gateway_id: { distance_m: [rssi, ...] } }
    data: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))

    for path in files:
        rows = load_csv(path)
        for row in rows:
            gw   = row["gateway_id"]
            dist = float(row["distance_m"])
            rssi = float(row["rssi"])
            data[gw][dist].append(rssi)

    if not data:
        print("  ✗  No data found.")
        return

    all_rssi_1m: list[float] = []
    all_far_slopes: list[float] = []

    for gw, by_dist in sorted(data.items()):
        print(f"\n  ── {gw} ──────────────────────────────")
        print(f"  {'dist (m)':>9}  {'n':>5}  {'mean dBm':>10}  {'std':>6}  {'min':>6}  {'max':>6}")
        print(f"  {'-'*9}  {'-'*5}  {'-'*10}  {'-'*6}  {'-'*6}  {'-'*6}")

        dists_sorted = sorted(by_dist.keys())
        means: list[float] = []
        for d in dists_sorted:
            vals = by_dist[d]
            m   = statistics.mean(vals)
            s   = statistics.stdev(vals) if len(vals) > 1 else 0.0
            means.append(m)
            print(f"  {d:>9.1f}  {len(vals):>5}  {m:>+10.1f}  {s:>6.1f}  {min(vals):>+6.1f}  {max(vals):>+6.1f}")

        # Estimate rssi at 1m reference
        if 1.0 in by_dist:
            rssi_1m = statistics.mean(by_dist[1.0])
        else:
            # Interpolate from nearest two points
            pairs = sorted((d, statistics.mean(v)) for d, v in by_dist.items())
            below = [(d, m) for d, m in pairs if d <= 1.0]
            above = [(d, m) for d, m in pairs if d >= 1.0]
            if below and above:
                d0, m0 = below[-1]; d1, m1 = above[0]
                t = (1.0 - d0) / (d1 - d0) if d1 != d0 else 0.5
                rssi_1m = m0 + t * (m1 - m0)
            elif below:
                rssi_1m = below[-1][1]
            else:
                rssi_1m = above[0][1]

        all_rssi_1m.append(rssi_1m)

        # Fit far-field slope (d > 1m)
        far_dists  = [d for d in dists_sorted if d > 1.0]
        far_means  = [statistics.mean(by_dist[d]) for d in far_dists]

        if len(far_dists) >= 2:
            # rssi = rssi_1m - slope * (d - 1)  →  (rssi_1m - rssi) = slope * (d - 1)
            xs = np.array([d - 1.0 for d in far_dists])
            ys = np.array([rssi_1m - m for m in far_means])
            slope_fit, intercept, r, p, se = linregress(xs, ys)
            print(f"\n  Far-field fit:  slope = {slope_fit:.2f} dBm/m   R² = {r**2:.3f}")
            all_far_slopes.append(slope_fit)
        else:
            print(f"\n  Not enough far-field points (need >1m, got {len(far_dists)})")
            slope_fit = 5.0  # fallback

        # Near-field: extrapolate d at -50 dBm from the linear near segment
        # rssi = rssi_1m + near_slope*(d-1)  →  d = 1 + (rssi - rssi_1m)/near_slope
        # We can't easily fit this without <1m data, so just report the crossover
        near_dists = [d for d in dists_sorted if d <= 1.0]
        near_means = [statistics.mean(by_dist[d]) for d in near_dists]
        if near_dists:
            rssi_at_half = statistics.mean(by_dist[0.5]) if 0.5 in by_dist else None
            if rssi_at_half:
                print(f"  Near-field:  rssi at 0.5m = {rssi_at_half:+.1f} dBm  (current BLE_NEAR_DIST_AT_REF target)")

        print(f"\n  Reference rssi at 1 m: {rssi_1m:+.1f} dBm")

    # ── Combined recommendations ────────────────────────────────────────────
    if all_rssi_1m:
        rec_tx = statistics.mean(all_rssi_1m)
        rec_far = statistics.mean(all_far_slopes) if all_far_slopes else 5.0

        # BLE_NEAR_DIST_AT_REF: we want the d where rssi == -50 using near model
        # With rssi = rssi_1m - rec_far*(d-1) we can at least tell what -50 corresponds to
        # For the near field the current model uses a linear d→rssi from 0.5→1m
        # Suggest leaving BLE_NEAR_RSSI = TX_POWER and BLE_NEAR_DIST_AT_REF = measured 0.5m mean
        rec_near_rssi = rec_tx
        # d at -50: rssi_1m - far_slope*(d-1) = -50  →  d = 1 + (rssi_1m+50)/far_slope
        # But near-field is a different steeper slope so clamp to ≤1
        d_at_minus50 = max(0.1, 1.0 - (rec_tx - (-50.0)) / max(rec_far, 0.5))

        print("\n")
        print("  ╔══════════════════════════════════════════════════════╗")
        print("  ║   Suggested values for backend/app/core/config.py   ║")
        print("  ╠══════════════════════════════════════════════════════╣")
        print(f"  ║  BLE_TX_POWER         = {rec_tx:+.1f}  (was -70)            ║")
        print(f"  ║  BLE_FAR_DBM_PER_M    = {rec_far:.2f}  (was 5.0)            ║")
        print(f"  ║  BLE_NEAR_RSSI        = {rec_near_rssi:+.1f}  (was -70)            ║")
        print(f"  ║  BLE_NEAR_DIST_AT_REF = {d_at_minus50:.2f}  (was 0.5)             ║")
        print("  ╚══════════════════════════════════════════════════════╝")
        print()
        print("  Paste these into config.py and restart the backend.")
        print("  Then run  python calibrate.py survey  to verify accuracy.")


# ── Survey analysis ─────────────────────────────────────────────────────────

def analyse_survey(path: Path, show_plot: bool = False):
    rows = load_csv(path)
    if not rows:
        print("  ✗  Empty file.")
        return

    # Per-point statistics
    by_point: dict[tuple[float, float], list[float]] = defaultdict(list)
    for r in rows:
        key = (float(r["actual_x"]), float(r["actual_y"]))
        by_point[key].append(float(r["error_m"]))

    errors_all = [float(r["error_m"]) for r in rows]

    print(f"\n  Loaded {len(rows)} estimates at {len(by_point)} grid points\n")
    print(f"  {'Actual pos':>15}  {'n':>4}  {'mean err':>9}  {'max err':>8}  {'<1m %':>7}")
    print(f"  {'-'*15}  {'-'*4}  {'-'*9}  {'-'*8}  {'-'*7}")

    for (ax, ay), errs in sorted(by_point.items()):
        mean_e = statistics.mean(errs)
        max_e  = max(errs)
        pct_1m = 100 * sum(1 for e in errs if e < 1.0) / len(errs)
        flag   = "✔" if mean_e < 1.0 else "⚠" if mean_e < 2.0 else "✗"
        print(f"  ({ax:4.1f}, {ay:4.1f}){'':<3}  {len(errs):>4}  {mean_e:>8.2f}m  {max_e:>7.2f}m  {pct_1m:>6.0f}%  {flag}")

    print(f"\n  Overall:  mean={statistics.mean(errors_all):.2f}m  "
          f"median={statistics.median(errors_all):.2f}m  "
          f"max={max(errors_all):.2f}m  "
          f"<1m={100*sum(1 for e in errors_all if e<1)/len(errors_all):.0f}%")

    _ascii_heatmap(by_point)

    if show_plot:
        _matplotlib_plot(rows)


def _ascii_heatmap(by_point: dict):
    """Draw a coarse ASCII map of error magnitude across the room."""
    try:
        from backend_config import STORE_WIDTH, STORE_HEIGHT
    except ImportError:
        # Reasonable defaults if can't import
        STORE_WIDTH, STORE_HEIGHT = 12.0, 5.0

    # Try to read from config directly
    try:
        import sys, importlib
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        cfg = importlib.import_module("app.core.config")
        STORE_WIDTH  = cfg.STORE_WIDTH
        STORE_HEIGHT = cfg.STORE_HEIGHT
    except Exception:
        STORE_WIDTH, STORE_HEIGHT = 12.0, 5.0

    COLS = 36
    ROWS_MAP = 12
    cell_w = STORE_WIDTH  / COLS
    cell_h = STORE_HEIGHT / ROWS_MAP

    # For each cell find the nearest measured point
    grid: list[list[float | None]] = [[None]*COLS for _ in range(ROWS_MAP)]
    for (ax, ay), errs in by_point.items():
        col = min(COLS-1, int(ax / cell_w))
        row = min(ROWS_MAP-1, int(ay / cell_h))
        mean_e = statistics.mean(errs)
        existing = grid[row][col]
        if existing is None or mean_e < existing:
            grid[row][col] = mean_e

    def char(e):
        if e is None:   return "·"
        if e < 0.5:     return "▓"  # excellent  < 0.5m
        if e < 1.0:     return "▒"  # good       < 1.0m
        if e < 1.5:     return "░"  # fair       < 1.5m
        return          "✗"         # poor       ≥ 1.5m

    print(f"\n  Error heatmap (room {STORE_WIDTH}×{STORE_HEIGHT} m):\n")
    border = "  +" + "-" * COLS + "+"
    print(border)
    for row in reversed(range(ROWS_MAP)):
        line = "".join(char(grid[row][col]) for col in range(COLS))
        print(f"  |{line}|")
    print(border)
    print(f"  {'0':>3}{' '*(COLS//2 - 2)}{STORE_WIDTH/2:.0f}m{' '*(COLS//2 - 3)}{STORE_WIDTH:.0f}m")
    print()
    print("  ▓ < 0.5m   ▒ < 1.0m   ░ < 1.5m   ✗ ≥ 1.5m   · not measured")


def _matplotlib_plot(rows: list[dict]):
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
    except ImportError:
        print("  (matplotlib not installed; skipping plot)")
        return

    ax_vals  = [float(r["actual_x"]) for r in rows]
    ay_vals  = [float(r["actual_y"]) for r in rows]
    ex_vals  = [float(r["est_x"])    for r in rows]
    ey_vals  = [float(r["est_y"])    for r in rows]
    err_vals = [float(r["error_m"])  for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Position Survey: Actual (●) vs Estimated (×)")
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
    ax.set_aspect("equal")

    norm = mcolors.Normalize(vmin=0, vmax=max(err_vals))
    cmap = plt.cm.RdYlGn_r

    for ax_v, ay_v, ex_v, ey_v, e in zip(ax_vals, ay_vals, ex_vals, ey_vals, err_vals):
        color = cmap(norm(e))
        ax.plot(ax_v, ay_v, "o", color="steelblue", markersize=8, zorder=3)
        ax.plot(ex_v, ey_v, "x", color=color, markersize=8, markeredgewidth=2, zorder=3)
        ax.plot([ax_v, ex_v], [ay_v, ey_v], "-", color=color, alpha=0.5, linewidth=1)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax, label="Position error (m)")

    ax.plot([], [], "o", color="steelblue", label="Actual")
    ax.plot([], [], "x", color="gray", label="Estimated")
    ax.legend()
    plt.tight_layout()
    plt.show()


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="IRE calibration analyser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    dp = sub.add_parser("distance", help="Fit RSSI-to-distance model from calibration CSVs")
    dp.add_argument("--file", nargs="+", help="Specific CSV files (default: all data/distance_*.csv)")

    sp = sub.add_parser("survey", help="Analyse position accuracy survey")
    sp.add_argument("--file", help="Specific CSV file (default: latest data/survey_*.csv)")
    sp.add_argument("--plot", action="store_true", help="Show matplotlib scatter plot")

    args = parser.parse_args()

    if args.mode == "distance":
        if args.file:
            files = [Path(f) for f in args.file]
        else:
            files = sorted(DATA_DIR.glob("distance_*.csv"))

        if not files:
            print(f"  ✗  No distance calibration files in {DATA_DIR}/")
            print(f"     Run:  python calibrate.py distance --gateway esp32_A --session YOUR_ID")
            return

        print(f"\n  Loading {len(files)} file(s):")
        for f in files:
            print(f"    {f.name}")
        analyse_distance(files)

    elif args.mode == "survey":
        path = Path(args.file) if args.file else latest("survey_*.csv")
        if not path or not path.exists():
            print(f"  ✗  No survey files in {DATA_DIR}/")
            print(f"     Run:  python calibrate.py survey --session YOUR_ID")
            return
        print(f"\n  Loading {path.name}")
        analyse_survey(path, show_plot=args.plot)


if __name__ == "__main__":
    main()
