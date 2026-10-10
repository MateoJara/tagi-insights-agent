"""Static charts for the insights report.

Run with: python -m src.charts
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.load_data import load_google_reviews, load_survey_responses
from src.metrics import ASPECT_COLUMNS, RECENT_MONTHS, aspect_change, monthly_means, rating_distribution

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "charts"

# Chart text is in Spanish because the report is read by restaurant owners.
ASPECT_LABELS = {
    "rating_food": "Comida",
    "rating_service": "Servicio",
    "rating_ambience": "Ambiente",
    "rating_value": "Precio",
}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
# Categorical slots in fixed order; a color follows its series, never its rank.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
ASPECT_COLORS = dict(zip(ASPECT_COLUMNS, SERIES))


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


def _save(fig, path, top=0.80):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, top))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_rating_distribution(reviews, path):
    counts = rating_distribution(reviews)
    total = counts.sum()
    fig, ax = _new_figure(
        "Distribución de calificaciones en Google",
        f"{total} reseñas",
        figsize=(8, 3.8),
    )
    positions = range(len(counts))
    ax.barh(positions, counts.values, height=0.55, color=SERIES[0])
    ax.set_yticks(positions, [f"{stars} ★" for stars in counts.index])
    ax.invert_yaxis()
    ax.set_xlim(0, counts.max() * 1.2)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    for position, count in zip(positions, counts.values):
        ax.text(
            count + counts.max() * 0.015,
            position,
            f"{count} · {count / total:.0%}",
            va="center",
            fontsize=10,
            color=INK,
        )
    return _save(fig, path)


def plot_monthly_trend(survey, path):
    monthly = monthly_means(survey)
    fig, ax = _new_figure(
        "Calificación promedio por aspecto, mes a mes",
        "Respuestas del formulario · escala de 1 a 5",
    )
    labels = [str(month) for month in monthly.index]
    for aspect in ASPECT_COLUMNS:
        ax.plot(
            labels,
            monthly[aspect],
            color=ASPECT_COLORS[aspect],
            linewidth=2,
            marker="o",
            markersize=6,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=ASPECT_LABELS[aspect],
            solid_capstyle="round",
        )
    ax.set_ylim(1, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    fig.legend(
        loc="upper left",
        bbox_to_anchor=(0.02, 0.84),
        ncols=len(ASPECT_COLUMNS),
        frameon=False,
        fontsize=10,
        labelcolor=INK_SECONDARY,
        handlelength=1.5,
        columnspacing=1.6,
    )
    return _save(fig, path, top=0.76)


def plot_aspect_change(survey, path, months=RECENT_MONTHS):
    changes = aspect_change(survey, months)
    fig, ax = _new_figure(
        "Antes y ahora por aspecto",
        f"Promedio de los últimos {months} meses frente al periodo anterior · ordenado por caída",
    )
    bar_height = 0.32
    positions = range(len(changes))
    series = (
        ("previous", "Antes", SERIES[0], -bar_height / 2 - 0.02),
        ("recent", f"Últimos {months} meses", SERIES[1], bar_height / 2 + 0.02),
    )
    for column, label, color, offset in series:
        centers = [position + offset for position in positions]
        ax.barh(centers, changes[column], height=bar_height, color=color, label=label)
        for center, value in zip(centers, changes[column]):
            ax.text(value + 0.05, center, f"{value:.2f}", va="center", fontsize=10, color=INK)
    ax.set_yticks(positions, [ASPECT_LABELS[aspect] for aspect in changes.index])
    ax.invert_yaxis()
    ax.set_xlim(0, 5.6)
    ax.set_xticks([0, 1, 2, 3, 4, 5])
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    fig.legend(
        loc="upper left",
        bbox_to_anchor=(0.02, 0.84),
        ncols=2,
        frameon=False,
        fontsize=10,
        labelcolor=INK_SECONDARY,
        handlelength=1.2,
    )
    return _save(fig, path, top=0.76)


def write_charts(survey, reviews, output_dir=OUTPUT_DIR):
    output_dir = Path(output_dir)
    return [
        plot_rating_distribution(reviews, output_dir / "rating_distribution.png"),
        plot_monthly_trend(survey, output_dir / "monthly_trend.png"),
        plot_aspect_change(survey, output_dir / "aspect_change.png"),
    ]


if __name__ == "__main__":
    survey, _ = load_survey_responses()
    reviews, _ = load_google_reviews()
    for chart_path in write_charts(survey, reviews):
        print(chart_path)
