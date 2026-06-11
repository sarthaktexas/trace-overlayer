# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib",
#   "numpy",
#   "pandas",
# ]
# ///
"""
Plot fluorescence traces from a plate-viewer CSV export.

Column naming convention (from the plate viewer):
    <Protein> [<Scientist> · <Date>] (<Experiment>, <Well1>, <Well2>, ...)
    <Protein> [<Scientist> · <Date>] (<Experiment>, <Well1>, ...) (SE)

The script groups traces by plate column (the numeric suffix of the wells,
e.g. "04"), treating each plate column as a distinct technical-repeat set.
Within each group it shows the effect of scientist and day via color / linestyle.

Usage:
    uv run plot_plate_fluorescence.py path/to/plate-viewer.csv

Output:
    <csv-directory>/<stem>.png
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Nature style
# ---------------------------------------------------------------------------

_NATURE_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7,
    "axes.titlesize": 8,
    "axes.labelsize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "axes.linewidth": 0.5,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.minor.width": 0.5,
    "ytick.minor.width": 0.5,
    "lines.linewidth": 0.75,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "axes.spines.top": False,
    "axes.spines.right": False,
}

mpl.rcParams.update(_NATURE_RC)
logging.getLogger("fontTools").setLevel(logging.ERROR)

_CATEGORICAL = [
    "#4E79A7",
    "#E15759",
    "#59A14F",
    "#F28E2B",
    "#76B7B2",
    "#EDC948",
    "#B07AA1",
    "#9C755F",
]

PALETTES = {
    "categorical": _CATEGORICAL,
    "diverging": mpl.colormaps["RdBu_r"].copy(),
    "sequential": LinearSegmentedColormap.from_list(
        "nature_sequential",
        ["#FFFFCC", "#FFEDA0", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"],
    ),
}

WORD_PNG_DPI = 600


def _apply(ax: plt.Axes) -> None:
    if hasattr(ax, "spines"):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="both", which="major", labelsize=6, width=0.5, length=2)
        ax.tick_params(axis="both", which="minor", width=0.5)
    else:
        ax.tick_params(labelsize=6, width=0.5, length=2)


def _savefig(fig: plt.Figure, path: str | Path, **kwargs) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_kw = dict(bbox_inches="tight", facecolor="white", **kwargs)
    fig.savefig(out.with_suffix(".png"), dpi=WORD_PNG_DPI, **save_kw)


# ---------------------------------------------------------------------------
# Column-name parser
# ---------------------------------------------------------------------------

_COL_RE = re.compile(
    r"^(?P<protein>[^\[]+?)\s*"
    r"\[(?P<scientist>[^\·]+?)\s*·\s*(?P<date>\S+)\]\s*"
    r"\((?P<experiment>[^,]+),\s*(?P<wells>[^)]+)\)"
    r"(?:\s*\(SE\))?$"
)


def parse_col(name: str) -> dict | None:
    m = _COL_RE.match(name.strip())
    if not m:
        return None
    wells = [w.strip() for w in m.group("wells").split(",")]
    col_nums = {re.sub(r"[A-Za-z]", "", w) for w in wells}
    plate_col = col_nums.pop() if len(col_nums) == 1 else "+".join(sorted(col_nums))
    return {
        "protein": m.group("protein").strip(),
        "scientist": m.group("scientist").strip(),
        "date": m.group("date").strip(),
        "experiment": m.group("experiment").strip(),
        "wells": wells,
        "plate_col": plate_col,
        "is_se": name.strip().endswith("(SE)"),
        "raw": name,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(subset=[df.columns[0]])
    df[df.columns[0]] = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    df = df.dropna(subset=[df.columns[0]])
    return df


def plot(csv_path: Path) -> None:
    df = load(csv_path)
    time = df.iloc[:, 0].values

    meta: dict[str, dict] = {}
    for col in df.columns[1:]:
        info = parse_col(col)
        if info:
            meta[col] = info

    def _key(info: dict) -> tuple:
        return (info["protein"], info["scientist"], info["date"], info["plate_col"])

    mean_cols: dict[tuple, str] = {}
    se_cols: dict[tuple, str] = {}
    for col, info in meta.items():
        k = _key(info)
        if info["is_se"]:
            se_cols[k] = col
        else:
            mean_cols[k] = col

    proteins = sorted({k[0] for k in mean_cols})
    scientist_date_pairs = sorted({(s, d) for (_, s, d, _) in mean_cols})
    n_panels = len(scientist_date_pairs)

    fig, axes = plt.subplots(
        1, n_panels,
        figsize=(3.0 * n_panels, 2.8),
        squeeze=False,
        sharey=True,
        sharex=True,
    )

    protein_color = {p: PALETTES["categorical"][i] for i, p in enumerate(proteins)}
    legend_handles: dict[str, object] = {}

    for col_idx, (scientist, date) in enumerate(scientist_date_pairs):
        ax = axes[0][col_idx]
        _apply(ax)

        combos = sorted({(p, pc) for (p, s, d, pc) in mean_cols if s == scientist and d == date})

        for protein, plate_col in combos:
            k = (protein, scientist, date, plate_col)
            if k not in mean_cols:
                continue
            y = pd.to_numeric(df[mean_cols[k]], errors="coerce").values
            mask = ~np.isnan(y)
            t, y = time[mask], y[mask]

            color = protein_color[protein]
            ax.plot(t, y, color=color, lw=0.9, alpha=0.8)

            if k in se_cols:
                ye = pd.to_numeric(df[se_cols[k]], errors="coerce").values[mask]
                ax.fill_between(t, y - ye, y + ye, color=color, alpha=0.12, lw=0)

            if protein not in legend_handles:
                legend_handles[protein] = plt.Line2D([], [], color=color, lw=1.5, label=protein)

        ax.set_title(f"{scientist}  ·  {date}", fontsize=7, fontweight="bold")
        ax.set_xlabel("Time (s)", fontsize=6)
        if col_idx == 0:
            ax.set_ylabel("Fluorescence (AU)", fontsize=6)

    fig.legend(
        handles=list(legend_handles.values()),
        loc="lower center",
        ncol=len(legend_handles),
        fontsize=5.5,
        frameon=False,
        bbox_to_anchor=(0.5, -0.04),
    )

    title = f"{', '.join(proteins)} across time and scientist"
    fig.suptitle(title, fontsize=7, y=1.01)
    fig.tight_layout()

    out_dir = csv_path.parent
    _savefig(fig, out_dir / csv_path.stem)
    print(f"Saved → {out_dir / csv_path.stem}.png")
    plt.close(fig)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run plot_plate_fluorescence.py <csv_path>")
        sys.exit(1)
    plot(Path(sys.argv[1]))
