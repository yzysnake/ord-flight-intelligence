"""Chart style: theme settings and axis formatters."""

import matplotlib as mpl
import matplotlib.pyplot as plt

from ordfi import viz


def test_use_style_sets_surface_grid_and_palette_order() -> None:
    with mpl.rc_context():
        viz.use_style()
        assert mpl.rcParams["axes.facecolor"] == viz.SURFACE
        assert mpl.rcParams["axes.grid.axis"] == "y"
        assert mpl.rcParams["grid.linestyle"] == "-"  # solid hairlines, never dashed
        colors = mpl.rcParams["axes.prop_cycle"].by_key()["color"]
        assert tuple(colors) == viz.CATEGORICAL


def test_axis_formatters() -> None:
    fig, ax = plt.subplots()
    viz.percent_axis(ax)
    viz.thousands_axis(ax, axis="x")
    assert ax.yaxis.get_major_formatter()(25, 0) == "25 %"
    assert ax.xaxis.get_major_formatter()(20_000, 0) == "20K"
    assert ax.xaxis.get_major_formatter()(0, 0) == "0"
    plt.close(fig)


def test_titles_add_a_subtitle_line() -> None:
    fig, ax = plt.subplots()
    viz.titles(ax, "Late departures", "Share 15+ min late")
    assert ax.get_title(loc="left") == "Late departures"
    assert [text.get_text() for text in ax.texts] == ["Share 15+ min late"]
    plt.close(fig)
