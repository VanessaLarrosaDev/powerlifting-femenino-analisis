"""
ESTILO VISUAL DEL PROYECTO
==========================
Paleta y ajustes de matplotlib para que todas las figuras del informe y de
los notebooks tengan un acabado homogeneo y legible.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# --- Paleta: morados y magentas como color principal, con apoyos neutros ---
MORADO = "#6C3FA4"
MORADO_CLARO = "#A47ACB"
MAGENTA = "#C2367F"
CORAL = "#E5734F"
AMBAR = "#E0A82E"
TEAL = "#2E8B8B"
AZUL = "#3B6EA5"
GRIS = "#6B6B76"
GRIS_CLARO = "#D8D8DE"
TINTA = "#241F31"

SECUENCIA = [MORADO, MAGENTA, TEAL, AMBAR, AZUL, CORAL, MORADO_CLARO, GRIS]

# Comparaciones de dos categorias (p. ej. mujeres vs referencia masculina)
PAR = {"mujeres": MAGENTA, "hombres": AZUL}

# Escala continua para mapas de calor y degradados
MAPA_CALOR = "magma_r"
MAPA_DIVERGENTE = "PuOr"


def aplicar() -> None:
    """Aplica el estilo del proyecto a todas las figuras posteriores."""
    mpl.rcParams.update({
        # Lienzo
        "figure.figsize": (11, 6),
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        # Tipografia
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlepad": 14,
        "axes.labelsize": 11,
        "axes.labelcolor": TINTA,
        "text.color": TINTA,
        # Ejes: solo las dos lineas necesarias
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": GRIS,
        "axes.linewidth": 0.9,
        "xtick.color": GRIS,
        "ytick.color": GRIS,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        # Rejilla discreta, solo horizontal
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRIS_CLARO,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.8,
        "axes.axisbelow": True,
        # Leyenda
        "legend.frameon": False,
        "legend.fontsize": 10,
        # Ciclo de color
        "axes.prop_cycle": mpl.cycler(color=SECUENCIA),
        "lines.linewidth": 2.2,
        "lines.markersize": 6,
    })


def titular(ax, titulo: str, subtitulo: str | None = None) -> None:
    """Pone titulo y, opcionalmente, un subtitulo explicativo mas discreto."""
    ax.set_title(titulo, loc="left", pad=18 if subtitulo else 12)
    if subtitulo:
        ax.text(0, 1.02, subtitulo, transform=ax.transAxes, fontsize=10,
                color=GRIS, va="bottom", ha="left")


def pie_de_fuente(fig, texto: str = "Fuente: OpenPowerlifting, Banco Mundial y PNUD") -> None:
    """Anade la atribucion de fuentes al pie de la figura."""
    fig.text(0.01, -0.02, texto, fontsize=8.5, color=GRIS, ha="left", va="top")


def guardar(fig, nombre: str, carpeta=None) -> None:
    """Guarda la figura en reports/figures con nombre normalizado."""
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as cfg
    destino = (carpeta or cfg.FIGURES) / f"{nombre}.png"
    fig.savefig(destino, facecolor="white")
    plt.close(fig)
    return destino
