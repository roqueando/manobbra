"""Tela de desenho do esquema e interação com o usuário.

Navegação:
  • ferramenta Selecionar — inserir/mover/ligar componentes (comportamento padrão);
  • ferramenta Mover (pan) — arrastar para deslocar a vista;
  • roda do mouse — rola vertical; Shift+roda — rola horizontal;
  • Ctrl+roda (ou botões +/-) — zoom;
  • botão do meio — pan em qualquer ferramenta.
"""

import tkinter as tk

from .. import theme
from ..model.components import COMPONENT_TYPES

GRID = theme.GRID

# Tamanho da "folha" em células.
SHEET_W = 160
SHEET_H = 100

MIN_GRID = 4
MAX_GRID = 60


def ortho_path(a, b):
    """Roteia um fio em "L/Z" entre dois pontos (Manhattan simples)."""
    x1, y1 = a
    x2, y2 = b
    mid = (x1 + x2) // 2
    return [(x1, y1), (mid, y1), (mid, y2), (x2, y2)]


def flatten(pts):
    out = []
    for p in pts:
        out.extend(p)
    return out


def dist_point_segment(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    qx, qy = ax + t * dx, ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


class SchematicCanvas(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, bg="white", highlightthickness=0)
        self.app = app

        # escala (célula em pixels)
        self.grid_px = GRID
        self.zoom_level = 1.0

        # ferramenta ativa
        self.tool = "select"      # "select" | "pan"
        self._panning = False

        # estado de interação (edição)
        self.wire_start = None    # (comp_id, term_name, anchor)
        self.wire_cursor = None
        self.selected_comp = None
        self.selected_wire = None
        self.drag_comp = None
        self.drag_offset = (0, 0)
        self._ghost_pos = None
        self._last_cursor = None

        # estado de interação (simulação)
        self.press_comp = None

        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_motion)
        self.bind("<Button-3>", self.on_right_click)

        # pan com botão do meio
        self.bind("<Button-2>", self._pan_start)
        self.bind("<B2-Motion>", self._pan_move)

        # roda do mouse (scroll / zoom com Ctrl)
        self.bind("<Button-4>", self.on_wheel)
        self.bind("<Button-5>", self.on_wheel)
        self.bind("<MouseWheel>", self.on_wheel)

    # ------------------------------------------------------------------ #
    # Escala / navegação
    # ------------------------------------------------------------------ #
    def _sheet_px(self):
        return (SHEET_W * self.grid_px, SHEET_H * self.grid_px)

    def zoom(self, factor):
        new_grid = int(round(self.grid_px * factor))
        new_grid = max(MIN_GRID, min(MAX_GRID, new_grid))
        if new_grid == self.grid_px:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        wx = self.canvasx(w / 2)
        wy = self.canvasy(h / 2)
        self.grid_px = new_grid
        self.zoom_level = self.grid_px / GRID
        self.redraw()
        W, H = self._sheet_px()
        self.xview_moveto(max(0.0, min(1.0, (wx - w / 2) / W)))
        self.yview_moveto(max(0.0, min(1.0, (wy - h / 2) / H)))
        self.app.update_status()

    def zoom_reset(self):
        self.grid_px = GRID
        self.zoom_level = 1.0
        self.redraw()
        self.xview_moveto(0)
        self.yview_moveto(0)
        self.app.update_status()

    def set_tool(self, tool):
        self.tool = tool
        self._panning = False
        if tool == "pan":
            self.configure(cursor="fleur")
        else:
            self.configure(cursor="")

    def on_wheel(self, e):
        ctrl = (e.state & 0x0004) != 0
        shift = (e.state & 0x0001) != 0
        if getattr(e, "num", None) in (4, 5):
            direction = 1 if e.num == 4 else -1
            step = 1
        else:  # Windows <MouseWheel>
            delta = getattr(e, "delta", 0)
            direction = 1 if delta > 0 else -1
            step = max(1, abs(delta) // 120)
        if ctrl:
            self.zoom(1.2 if direction > 0 else 1 / 1.2)
        elif shift:
            self.xview_scroll(-direction * step, "units")
        else:
            self.yview_scroll(-direction * step, "units")

    def _pan_start(self, e):
        self.scan_mark(e.x, e.y)

    def _pan_move(self, e):
        self.scan_dragto(e.x, e.y, gain=1)

    # ------------------------------------------------------------------ #
    # Desenho
    # ------------------------------------------------------------------ #
    def redraw(self):
        self.delete("all")
        self._draw_grid()
        self._draw_scene()
        W, H = self._sheet_px()
        self.configure(scrollregion=(0, 0, W, H))

    def _draw_grid(self):
        c = theme.COLORS
        W, H = self._sheet_px()
        g = self.grid_px
        for x in range(0, W + 1, g):
            color = c["grid_major"] if (x // g) % 5 == 0 else c["grid"]
            self.create_line(x, 0, x, H, fill=color)
        for y in range(0, H + 1, g):
            color = c["grid_major"] if (y // g) % 5 == 0 else c["grid"]
            self.create_line(0, y, W, y, fill=color)

    def _draw_scene(self):
        circuit = self.app.circuit
        sim = self.app.sim_state if self.app.mode == "simulate" else None

        # 1) destaque da ligação selecionada (por baixo)
        if self.selected_wire:
            pts = self.wire_path(self.selected_wire)
            if pts:
                self.create_line(*flatten(pts), fill=theme.COLORS["selection"],
                                 width=7, capstyle="round", tags="scene")

        # 2) fios
        for w in circuit.wires:
            self.draw_wire(w, sim)

        # 3) componentes
        for comp in circuit.components.values():
            comp.draw(self, sim, self.grid_px)

        # 4) seleção de componente / preview de fio / ghost
        if self.selected_comp:
            x0, y0, x1, y1 = self.selected_comp.bbox(self.grid_px)
            self.create_rectangle(x0 - 5, y0 - 5, x1 + 5, y1 + 5,
                                  outline=theme.COLORS["selection"],
                                  dash=(3, 3), width=1, tags="scene")

        if self.wire_start:
            a = circuit.endpoint_position(self.wire_start[0], self.wire_start[1],
                                          self.wire_start[2], self.grid_px)
            if a:
                end = self.wire_cursor or a
                pts = ortho_path(a, end)
                self.create_line(*flatten(pts), fill=theme.COLORS["selection"],
                                 width=2, dash=(4, 4), tags="scene")

        if self.app.pending_type and self._ghost_pos:
            gx, gy = self._ghost_pos
            cls = COMPONENT_TYPES[self.app.pending_type]
            w = cls.footprint[0] * self.grid_px
            h = cls.footprint[1] * self.grid_px
            self.create_rectangle(gx - w / 2, gy - h / 2, gx + w / 2, gy + h / 2,
                                  outline=theme.COLORS["ghost"], dash=(3, 3),
                                  tags="scene")

    def draw_wire(self, w, sim):
        pts = self.wire_path(w)
        if not pts:
            return
        if sim is not None:
            color = theme.wire_color(sim.term_status(w.a[0], w.a[1]))
        else:
            color = theme.COLORS["wire"]
        self.create_line(*flatten(pts), fill=color, width=2,
                         capstyle="round", joinstyle="round", tags="scene")

    def wire_path(self, w):
        a = self.app.circuit.endpoint_position(w.a[0], w.a[1], w.anchor_a, self.grid_px)
        b = self.app.circuit.endpoint_position(w.b[0], w.b[1], w.anchor_b, self.grid_px)
        if a is None or b is None:
            return None
        return ortho_path(a, b)

    # ------------------------------------------------------------------ #
    # Hit-testing
    # ------------------------------------------------------------------ #
    def hit_component(self, x, y):
        for comp in reversed(list(self.app.circuit.components.values())):
            if comp.contains(x, y, self.grid_px):
                return comp
        return None

    def hit_terminal(self, x, y):
        r = max(4, int(self.grid_px * 0.35))
        for comp in self.app.circuit.components.values():
            for t in comp.terminals:
                px, py = comp.term_px(t.name, self.grid_px)
                if abs(px - x) <= r and abs(py - y) <= r:
                    return (comp.id, t.name)
        return None

    def hit_source_line(self, x, y):
        """Retorna (comp_id, condutor, anchor) se o clique tocar um barramento."""
        tol = 0.4
        for comp in self.app.circuit.components.values():
            if not comp.is_source:
                continue
            lx, ly = comp.local_cell(x, y, self.grid_px)
            for t in comp.terminals:
                if abs(ly - t.dy) <= tol and -3.5 <= lx <= 3.5:
                    return (comp.id, t.name, (round(lx), t.dy))
        return None

    def hit_wire(self, x, y, tol=6):
        best = None
        bestd = tol
        for w in self.app.circuit.wires:
            pts = self.wire_path(w)
            if not pts:
                continue
            for i in range(len(pts) - 1):
                d = dist_point_segment((x, y), pts[i], pts[i + 1])
                if d < bestd:
                    bestd = d
                    best = w
        return best

    # ------------------------------------------------------------------ #
    # Eventos de mouse
    # ------------------------------------------------------------------ #
    def _pos(self, e):
        return int(self.canvasx(e.x)), int(self.canvasy(e.y))

    def on_click(self, e):
        x, y = self._pos(e)
        circuit = self.app.circuit

        if self.app.mode == "simulate":
            comp = self.hit_component(x, y)
            if comp and comp.is_button:
                comp.pressed = True
                self.press_comp = comp
                self.app.refresh_sim()
            elif comp and comp.is_toggle:
                comp.toggle()
                self.app.refresh_sim()
            return

        # ---- modo edição ----
        if self.tool == "pan":
            self._panning = True
            self.scan_mark(e.x, e.y)
            return

        if self.app.pending_type:
            gx, gy = round(x / self.grid_px), round(y / self.grid_px)
            circuit.add_component(self.app.pending_type, gx, gy,
                                 config=self.app.pending_config)
            self.app.clear_pending()
            self.app.on_circuit_changed()
            self.redraw()
            return

        term = self.hit_terminal(x, y)
        if term:
            endpoint = (term[0], term[1], None)
        else:
            endpoint = self.hit_source_line(x, y)
        if endpoint:
            if self.wire_start is None:
                self.wire_start = endpoint
                self.redraw()
            else:
                if (endpoint[0], endpoint[1]) != (self.wire_start[0], self.wire_start[1]):
                    circuit.add_wire(self.wire_start, endpoint)
                    self.app.on_circuit_changed()
                self.wire_start = None
                self.wire_cursor = None
                self.redraw()
            return

        comp = self.hit_component(x, y)
        if comp:
            self.selected_comp = comp
            self.selected_wire = None
            self.drag_comp = comp
            self.drag_offset = (comp.x * self.grid_px - x, comp.y * self.grid_px - y)
            self.redraw()
            self.app.update_status()
            return

        w = self.hit_wire(x, y)
        if w:
            self.selected_wire = w
            self.selected_comp = None
            self.redraw()
            self.app.update_status()
            return

        self.selected_comp = None
        self.selected_wire = None
        self.redraw()
        self.app.update_status()

    def on_drag(self, e):
        if self._panning:
            self.scan_dragto(e.x, e.y, gain=1)
            return
        if self.app.mode != "edit":
            return
        x, y = self._pos(e)
        if self.wire_start:
            self.wire_cursor = (x, y)
            self.redraw()
        elif self.drag_comp:
            nx = x + self.drag_offset[0]
            ny = y + self.drag_offset[1]
            self.drag_comp.x = round(nx / self.grid_px)
            self.drag_comp.y = round(ny / self.grid_px)
            self.app.on_circuit_changed()
            self.redraw()

    def on_release(self, e):
        if self._panning:
            self._panning = False
            return
        if self.app.mode == "simulate":
            if self.press_comp:
                self.press_comp.pressed = False
                self.press_comp = None
                self.app.refresh_sim()
            return
        self.drag_comp = None

    def on_motion(self, e):
        if self.app.mode != "edit":
            return
        x, y = self._pos(e)
        changed = False
        if self.app.pending_type:
            gp = (round(x / self.grid_px) * self.grid_px, round(y / self.grid_px) * self.grid_px)
            if self._ghost_pos != gp:
                self._ghost_pos = gp
                changed = True
        elif self.wire_start:
            if self._last_cursor != (x, y):
                self._last_cursor = (x, y)
                self.wire_cursor = (x, y)
                changed = True
        if changed:
            self.redraw()

    def on_right_click(self, e):
        if self.app.mode != "edit":
            return
        x, y = self._pos(e)
        if self.wire_start or self.app.pending_type:
            self.cancel_action()
            return
        comp = self.hit_component(x, y)
        if comp:
            self.app.circuit.remove_component(comp.id)
            self.app.on_circuit_changed()
            self.redraw()
            return
        w = self.hit_wire(x, y)
        if w:
            self.app.circuit.remove_wire(w.id)
            self.app.on_circuit_changed()
            self.redraw()
            return

    # ------------------------------------------------------------------ #
    # Ações auxiliares
    # ------------------------------------------------------------------ #
    def delete_selection(self):
        if self.selected_comp:
            self.app.circuit.remove_component(self.selected_comp.id)
            self.selected_comp = None
            self.app.on_circuit_changed()
            self.redraw()
        elif self.selected_wire:
            self.app.circuit.remove_wire(self.selected_wire.id)
            self.selected_wire = None
            self.app.on_circuit_changed()
            self.redraw()

    def cancel_action(self):
        self.wire_start = None
        self.wire_cursor = None
        self._last_cursor = None
        self.selected_comp = None
        self.selected_wire = None
        self.app.clear_pending()
        self.redraw()
        self.app.update_status()
