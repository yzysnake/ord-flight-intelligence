"""Chart style for notebooks and reports: the validated reference palette and a matplotlib theme.

Light mode only (static figures). Rules the helpers encode:

- categorical hues are assigned in the fixed order of ``CATEGORICAL``, never cycled past eight;
- magnitude uses the single-hue ``SEQUENTIAL`` blue ramp;
- one series takes ``CATEGORICAL[0]``, and context takes ``DEEMPHASIS``;
- text uses the ink tokens, never a series color;
- gridlines are solid hairlines, and there is never a second y-axis.

Slots 1–3 pass the colour-vision checks for any pairing (more series: facet or fold to
"Other"). The ramp's steps from ``#86b6ef`` to ``#0d366b`` pass as an ordinal scale.
"""

from __future__ import annotations

import matplotlib as mpl
from cycler import cycler
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, PercentFormatter

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
DEEMPHASIS = "#c3c2b7"
CATEGORICAL = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948",
)  # fmt: skip
BLUE_RAMP = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
    "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
)  # fmt: skip
SEQUENTIAL = LinearSegmentedColormap.from_list("ordfi_blue", BLUE_RAMP)


def use_style() -> None:
    """Apply the project theme: light surface, recessive y-axis hairlines, 2 px lines, no boxes."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "figure.constrained_layout.use": True,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "text.color": TEXT,
            "axes.titlecolor": TEXT,
            "axes.titlelocation": "left",
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.edgecolor": BASELINE,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "axes.prop_cycle": cycler(color=CATEGORICAL),
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "xtick.color": BASELINE,
            "ytick.color": BASELINE,
            "xtick.labelcolor": TEXT_SECONDARY,
            "ytick.labelcolor": TEXT_SECONDARY,
            "lines.linewidth": 2,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "legend.frameon": False,
            "legend.labelcolor": TEXT_SECONDARY,
        }
    )


def titles(ax: Axes, title: str, subtitle: str | None = None) -> None:
    """A left-aligned title with an optional secondary line (definition, period) under it."""
    ax.set_title(title, loc="left", pad=24 if subtitle else 8)
    if subtitle:
        ax.annotate(
            subtitle, xy=(0, 1), xycoords="axes fraction", xytext=(0, 8),
            textcoords="offset points", color=TEXT_SECONDARY, fontsize=10, va="bottom",
        )  # fmt: skip


def percent_axis(ax: Axes, axis: str = "y", decimals: int = 0) -> None:
    """Format an axis holding percentages (0–100) as ``25 %``-style ticks."""
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(PercentFormatter(100, decimals=decimals, symbol=" %"))


def thousands_axis(ax: Axes, axis: str = "y") -> None:
    """Compact large tick values: 0, 20K, 40K."""
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_formatter(
        FuncFormatter(lambda value, _: "0" if value == 0 else f"{value / 1000:,.0f}K")
    )
