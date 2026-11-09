"""Tema visual e constantes do editor."""

# Tamanho da célula da grade, em pixels.
GRID = 20

COLORS = {
    "bg": "#f7f8fa",
    "grid": "#e8ebf0",
    "grid_major": "#d4dae3",
    "component": "#212a35",
    "label": "#212a35",
    "terminal": "#ffffff",
    "terminal_border": "#212a35",
    "wire": "#6b7280",
    "live": "#d62828",
    "neutral": "#1565c0",
    "earth": "#2e7d32",
    "short": "#f48c06",
    "float": "#9aa3ad",
    "selection": "#0a84ff",
    "coil": "#eef1f5",
    "coil_on": "#ff7a7a",
    "lamp_on": "#ffd43b",
    "motor_on": "#69db7c",
    "source": "#eef1f5",
    "contact": "#ffffff",
    "closed": "#d62828",
    "ghost": "#a5adb8",
}


def terminal_color(status: str) -> str:
    """Cor do terminal conforme seu potencial."""
    return {
        "live": COLORS["live"],
        "neutral": COLORS["neutral"],
        "earth": COLORS["earth"],
        "short": COLORS["short"],
        "float": COLORS["terminal"],
    }[status]


def wire_color(status: str) -> str:
    """Cor do fio conforme o potencial da rede à qual pertence."""
    return {
        "live": COLORS["live"],
        "neutral": COLORS["neutral"],
        "earth": COLORS["earth"],
        "short": COLORS["short"],
        "float": COLORS["wire"],
    }[status]
