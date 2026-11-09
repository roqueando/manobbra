"""Widgets auxiliares de interface."""

import tkinter as tk


class ScrollableFrame(tk.Frame):
    """Frame rolável verticalmente, com conteúdo em `self.inner`.

    Use `self.inner` como pai dos widgets e chame `enable_wheel()` ao final
    para que a roda do mouse role o conteúdo quando o cursor estiver sobre ele.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        if getattr(event, "num", None) in (4, 5):
            self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        else:  # Windows <MouseWheel>
            delta = getattr(event, "delta", 0)
            self.canvas.yview_scroll(-1 if delta > 0 else 1, "units")

    def enable_wheel(self):
        """Liga a roda do mouse em todos os widgets internos (recursivo)."""
        self._bind_recursive(self)

    def _bind_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_wheel)
        widget.bind("<Button-4>", self._on_wheel)
        widget.bind("<Button-5>", self._on_wheel)
        for child in widget.winfo_children():
            self._bind_recursive(child)
