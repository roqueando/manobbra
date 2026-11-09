"""Biblioteca visual de componentes: ícones desenhados + botão clicável."""

import tkinter as tk

from ..model.components import create_component

# Nome de exemplo usado dentro do símbolo de cada ícone.
ICON_NAMES = {
    "source": "",
    "button_no": "S",
    "button_nc": "S",
    "coil": "K1",
    "contact_no": "K1",
    "contact_nc": "K1",
    "lamp": "H",
    "motor": "M",
    "breaker_1p": "Q1",
    "breaker_3p": "Q1",
    "motor_breaker": "Q1",
    "thermal": "F1",
    "terminal": "X1",
    "emergency": "S0",
    "contact_no_3p": "K1",
}


def _icon_grid(comp, height):
    """Escolhe a escala do símbolo para caber na altura do ícone."""
    span = max(comp.footprint[1], 3)
    return max(3, min(8, (height - 24) // span))


def draw_component_icon(canvas, type_key, config=None):
    """Desenha o símbolo de um componente (estado normal) no centro do canvas."""
    comp = create_component(type_key, 0, 0, 0, config=config)
    comp.name = ICON_NAMES.get(type_key, "")
    if type_key in ("contact_no", "contact_nc"):
        comp.coil_name = "K1"
    w = canvas.winfo_reqwidth() or 96
    h = canvas.winfo_reqheight() or 64
    g = _icon_grid(comp, h)
    comp.draw_symbol(canvas, w // 2, h // 2, None, g, "icon")


class ComponentIconButton(tk.Frame):
    """Item da biblioteca: ícone + nome, clicável."""

    def __init__(self, parent, type_key, label, command, icon_size=(96, 64),
                 config=None):
        super().__init__(parent, bd=1, relief="flat")
        self.canvas = tk.Canvas(self, width=icon_size[0], height=icon_size[1],
                                highlightthickness=0, bg="white")
        self.canvas.pack()
        draw_component_icon(self.canvas, type_key, config)
        self.label = tk.Label(self, text=label, font=("Helvetica", 10))
        self.label.pack(pady=(2, 0))

        handler = lambda e: command()  # noqa: E731
        self.bind("<Button-1>", handler)
        self.canvas.bind("<Button-1>", handler)
        self.canvas.tag_bind("icon", "<Button-1>", handler)
        self.label.bind("<Button-1>", handler)
        for w in (self, self.canvas, self.label):
            w.configure(cursor="hand2")
