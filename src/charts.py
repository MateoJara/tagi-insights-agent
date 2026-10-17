"""Static charts for the insights report.

Run with: python -m src.charts
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.load_data import SAMPLE_DIR, load_google_reviews
from src.metrics import monthly_reviews, rating_distribution

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "charts"

# Chart text is in Spanish because the report is read by business owners.
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = "#2a78d6"


def _new_figure(title, subtitle, figsize=(8, 4.5)):
    fig, ax = plt.subplots(figsize=figsize, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, length=0, labelsize=10)
    fig.text(0.02, 0.96, title, fontsize=14, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.89, subtitle, fontsize=10, color=INK_SECONDARY, va="top")
    return fig, ax


def _save(fig, path, top=0.82):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, top))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def _month_labels(index):
    """'ene 2025' at each January and at the first month, the bare month elsewhere."""
    return [
        f"{MONTHS[m.month - 1]}\n{m.year}" if i == 0 or m.month == 1 else MONTHS[m.month - 1]
        for i, m in enumerate(index)
    ]


def plot_rating_distribution(reviews, path):
    counts = rating_distribution(reviews)
    total = counts.sum()
    fig, ax = _new_figure("Distribución de calificaciones en Google", f"{total} reseñas", figsize=(8, 3.8))
    positions = range(len(counts))
    ax.barh(positions, counts.values, height=0.55, color=SERIES)
    ax.set_yticks(positions, [f"{stars} ★" for stars in counts.index])
    ax.invert_yaxis()
    ax.set_xlim(0, counts.max() * 1.25)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    for position, count in zip(positions, counts.values):
        ax.text(count + counts.max() * 0.015, position, f"{count} · {count / total:.1%}",
                va="center", fontsize=10, color=INK)
    return _save(fig, path)


def plot_monthly_rating(reviews, path):
    monthly = monthly_reviews(reviews)
    fig, ax = _new_figure("Estrellas promedio, mes a mes", "Reseñas de Google · escala de 1 a 5")
    positions = range(len(monthly))
    ax.plot(positions, monthly["mean_rating"], color=SERIES, linewidth=2, marker="o", markersize=5,
            markeredgecolor=SURFACE, markeredgewidth=1.5, solid_capstyle="round")
    ax.set_ylim(1, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xticks(positions, _month_labels(monthly.index))
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    return _save(fig, path)


def plot_monthly_volume(reviews, path):
    monthly = monthly_reviews(reviews)
    fig, ax = _new_figure("Reseñas por mes", "Cuántas reseñas nuevas recibió el negocio cada mes")
    positions = range(len(monthly))
    ax.bar(positions, monthly["n_reviews"], width=0.6, color=SERIES)
    ax.set_xticks(positions, _month_labels(monthly.index))
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    return _save(fig, path)


def write_charts(reviews, output_dir=OUTPUT_DIR):
    output_dir = Path(output_dir)
    return [
        plot_rating_distribution(reviews, output_dir / "rating_distribution.png"),
        plot_monthly_rating(reviews, output_dir / "monthly_rating.png"),
        plot_monthly_volume(reviews, output_dir / "monthly_volume.png"),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the report charts as PNG files.")
    parser.add_argument("--reviews", default=SAMPLE_DIR / "google_reviews.csv")
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    reviews, _ = load_google_reviews(args.reviews)
    for chart_path in write_charts(reviews, args.output_dir):
        print(chart_path)


if __name__ == "__main__":
    main()
