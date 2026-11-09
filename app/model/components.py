"""Componentes elétricos: símbolos (IEC 60617 / QElectroTech), terminais e lógica.

Este módulo NÃO importa tkinter — o desenho recebe um canvas como parâmetro,
o que permite testar a lógica de simulação sem interface gráfica.

Convenção de orientação (conforme QElectroTech/IEC): contatos, botoeiras,
disjuntores, contator, relé térmico e cargas são desenhados na **vertical**
(terminais no topo e na base). Apenas as fontes (barramentos de força) são
linhas contínuas horizontais.
"""

from .. import theme

GRID = theme.GRID  # tamanho padrão da célula


class Terminal:
    """Ponto de conexão de um componente (deslocamento em células).

    `kind` identifica o tipo de potencial quando o terminal pertence a uma
    fonte: "phase", "neutral" ou "earth". Para os demais componentes é None.
    """

    __slots__ = ("name", "dx", "dy", "kind", "phase_name")

    def __init__(self, name, dx, dy, kind=None):
        self.name = name
        self.dx = dx
        self.dy = dy
        self.kind = kind
        self.phase_name = name if kind == "phase" else None


class _RotatedCanvas:
    """Proxy que rotaciona as coordenadas das primitivas em torno de um centro.

    Os textos não são rotacionados (Tkinter não gira fontes nativamente); eles
    são apenas realocados para acompanhar o símbolo.
    """

    def __init__(self, cv, cx, cy, rotation):
        self._cv = cv
        self.cx = cx
        self.cy = cy
        self.rotation = rotation % 360

    def _t(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        r = self.rotation
        if r == 90:
            return (self.cx + dy, self.cy - dx)
        if r == 180:
            return (self.cx - dx, self.cy - dy)
        if r == 270:
            return (self.cx - dy, self.cy + dx)
        return (x, y)

    def _pts(self, coords):
        out = []
        for i in range(0, len(coords), 2):
            tx, ty = self._t(coords[i], coords[i + 1])
            out.extend((tx, ty))
        return out

    def _box(self, x0, y0, x1, y1):
        ax, ay = self._t(x0, y0)
        bx, by = self._t(x1, y1)
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def create_line(self, *args, **kw):
        return self._cv.create_line(*self._pts(args), **kw)

    def create_oval(self, *args, **kw):
        return self._cv.create_oval(*self._box(*args), **kw)

    def create_rectangle(self, *args, **kw):
        return self._cv.create_rectangle(*self._box(*args), **kw)

    def create_arc(self, *args, **kw):
        return self._cv.create_arc(*self._box(*args), **kw)

    def create_polygon(self, *args, **kw):
        return self._cv.create_polygon(*self._pts(args), **kw)

    def create_text(self, x, y, **kw):
        tx, ty = self._t(x, y)
        return self._cv.create_text(tx, ty, **kw)


class Component:
    """Classe base de todos os componentes."""

    type_key = "component"
    name_prefix = None        # ex.: "S", "K", "H", "M", "Q", "F", "X"
    footprint = (4, 4)        # (largura, altura) em células, p/ área de clique/ghost
    is_switch = False
    is_load = False
    is_source = False
    is_button = False
    is_toggle = False         # dispositivos manuais que alternam (disjuntores, térmico...)
    terminals_spec = []       # [(nome, dx, dy), ...]

    def __init__(self, comp_id, x, y, config=None):
        self.id = comp_id
        self.x = x            # posição do centro, em células
        self.y = y
        self.config = config
        self.name = ""
        self.coil_name = "K1"  # contator ao qual um contato pertence
        self.pressed = False
        self.selected = False
        self.sim_closed = False
        self.sim_energized = False
        self.rotation = 0
        self.terminals = [Terminal(*spec) for spec in self.terminals_spec]

    # ------------------------------------------------------------------ #
    # Posições (dependem da escala `grid`)
    # ------------------------------------------------------------------ #
    def _rot(self, dx, dy):
        if self.rotation == 90:
            return (dy, -dx)
        if self.rotation == 180:
            return (-dx, -dy)
        if self.rotation == 270:
            return (-dy, dx)
        return (dx, dy)

    def term(self, name):
        for t in self.terminals:
            if t.name == name:
                return t
        raise KeyError(f"Terminal desconhecido: {name}")

    def term_px(self, name, grid=GRID):
        t = self.term(name)
        dx, dy = self._rot(t.dx * grid, t.dy * grid)
        return (self.x * grid + dx, self.y * grid + dy)

    def anchor_px(self, dx, dy, grid=GRID):
        rx, ry = self._rot(dx * grid, dy * grid)
        return (self.x * grid + rx, self.y * grid + ry)

    def local_cell(self, px, py, grid=GRID):
        dx = (px - self.x * grid) / grid
        dy = (py - self.y * grid) / grid
        if self.rotation == 90:
            dx, dy = -dy, dx
        elif self.rotation == 180:
            dx, dy = -dx, -dy
        elif self.rotation == 270:
            dx, dy = dy, -dx
        return dx, dy

    def bbox(self, grid=GRID):
        pts = []
        for t in self.terminals:
            dx, dy = self._rot(t.dx * grid, t.dy * grid)
            pts.append((self.x * grid + dx, self.y * grid + dy))
        hw = self.footprint[0] // 2 * grid
        hh = self.footprint[1] // 2 * grid
        for fx, fy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            rx, ry = self._rot(fx, fy)
            pts.append((self.x * grid + rx, self.y * grid + ry))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def contains(self, px, py, grid=GRID, pad=4):
        x0, y0, x1, y1 = self.bbox(grid)
        return (x0 - pad) <= px <= (x1 + pad) and (y0 - pad) <= py <= (y1 + pad)

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    def is_closed(self, coil_states):
        raise NotImplementedError

    def display_label(self):
        return self.name

    def visual_closed(self, sim):
        if sim is not None:
            return self.sim_closed
        return self.is_closed({})

    def visual_energized(self, sim):
        return self.sim_energized if sim is not None else False

    def conducting_pairs(self, coil_states):
        return []

    def load_energized(self, roots, phase_nets, neutral_nets):
        return _pair_energized(roots.get("t1"), roots.get("t2"), phase_nets, neutral_nets)

    def toggle(self):
        pass

    def reset_interaction(self):
        self.pressed = False
        self.sim_energized = False
        self.sim_closed = False

    # ------------------------------------------------------------------ #
    # Serialização
    # ------------------------------------------------------------------ #
    def to_dict(self):
        return {
            "type": self.type_key,
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "name": self.name,
            "coil_name": self.coil_name,
            "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, d):
        c = cls(d["id"], d["x"], d["y"])
        c.name = d.get("name", "")
        c.coil_name = d.get("coil_name", "K1")
        c.rotation = d.get("rotation", 0)
        return c

    # ------------------------------------------------------------------ #
    # Desenho
    # ------------------------------------------------------------------ #
    def draw(self, cv, sim, grid=GRID):
        cx, cy = self.x * grid, self.y * grid
        target = _RotatedCanvas(cv, cx, cy, self.rotation) if self.rotation else cv
        self.draw_symbol(target, cx, cy, sim, grid, "scene")
        self.draw_terminals(cv, sim, grid)

    def draw_terminals(self, cv, sim, grid=GRID):
        r = max(3, int(grid * 0.2))
        for t in self.terminals:
            px, py = self.term_px(t.name, grid)
            draw_terminal(cv, sim, self.id, t.name, px, py, r)

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        raise NotImplementedError


def _pair_energized(a, b, phase_nets, neutral_nets):
    """Energização de uma carga de 2 terminais (fase↔neutro ou fase↔fase)."""
    for nets in phase_nets.values():
        if (a in nets and b in neutral_nets) or (b in nets and a in neutral_nets):
            return True
    phases = list(phase_nets.values())
    for i in range(len(phases)):
        for j in range(i + 1, len(phases)):
            if (a in phases[i] and b in phases[j]) or (b in phases[i] and a in phases[j]):
                return True
    return False


def draw_terminal(cv, sim, comp_id, tname, px, py, r=4):
    if sim is not None:
        status = sim.term_status(comp_id, tname)
    else:
        status = "float"
    fill = theme.terminal_color(status)
    cv.create_oval(
        px - r, py - r, px + r, py + r,
        fill=fill, outline=theme.COLORS["terminal_border"], width=2, tags="scene",
    )


# ====================================================================== #
# Primitivas de desenho (verticais, IEC 60617 / QElectroTech)
# ====================================================================== #
def _hinge(cv, x, y, g, tag):
    c = theme.COLORS
    r = max(2, int(g * 0.14))
    cv.create_oval(x - r, y - r, x + r, y + r,
                   fill=c["component"], outline=c["component"], tags=tag)


def _contact_v(cv, cx, top_y, bot_y, closed, nc, sim, g, tag):
    """Contato vertical: NA (nc=False) ou NF (nc=True).

    O contato móvel pivota perto do topo. Em repouso:
      • NA: aberto (braço desce à esquerda, sem tocar);
      • NF: fechado (braço desce à direita e encosta numa barra fixa).
    """
    c = theme.COLORS
    hinge = top_y + int(0.5 * g)
    join = bot_y - int(0.5 * g)

    cv.create_line(cx, top_y, cx, hinge, fill=c["component"], width=2, tags=tag)
    cv.create_line(cx, join, cx, bot_y, fill=c["component"], width=2, tags=tag)
    _hinge(cv, cx, hinge, g, tag)

    arm = c["closed"] if (closed and sim is not None) else c["component"]
    if closed:
        if nc:
            cv.create_line(cx, hinge, cx + int(0.5 * g), hinge,
                           fill=c["component"], width=2, tags=tag)
            cv.create_line(cx, join, cx + int(0.5 * g), hinge, fill=arm, width=3, tags=tag)
        else:
            cv.create_line(cx, join, cx, hinge, fill=arm, width=3, tags=tag)
    else:
        cv.create_line(cx, join, cx - int(0.5 * g), hinge,
                       fill=c["component"], width=3, tags=tag)


def _breaker_pole_v(cv, cx, top_y, bot_y, closed, sim, g, tag):
    """Polo de disjuntor vertical: contato + marca de disparo '×'."""
    c = theme.COLORS
    hinge = top_y + int(0.5 * g)
    join = bot_y - int(0.5 * g)

    cv.create_line(cx, top_y, cx, hinge, fill=c["component"], width=2, tags=tag)
    _cross_mark(cv, cx, top_y + int(0.25 * g), g, tag)
    cv.create_line(cx, join, cx, bot_y, fill=c["component"], width=2, tags=tag)
    _hinge(cv, cx, hinge, g, tag)

    arm = c["closed"] if (closed and sim is not None) else c["component"]
    if closed:
        cv.create_line(cx, join, cx, hinge, fill=arm, width=3, tags=tag)
    else:
        cv.create_line(cx, join, cx - int(0.5 * g), hinge,
                       fill=c["component"], width=3, tags=tag)


def _heater_line(cv, cx, top_y, bot_y, g, tag, sim, comp_id, term_in):
    """Polo do relé térmico vertical (QET): linha + aquecedor à direita."""
    c = theme.COLORS
    mid = (top_y + bot_y) // 2
    hw = max(2, int(0.3 * g))
    color = c["component"]
    if sim is not None:
        color = theme.wire_color(sim.term_status(comp_id, term_in))
    cv.create_line(cx, top_y, cx, bot_y, fill=color, width=2, tags=tag)
    cv.create_rectangle(cx, mid - hw, cx + int(0.35 * g), mid + hw,
                        fill=c["contact"], outline=c["component"], width=2, tags=tag)


def _cross_mark(cv, x, y, g, tag):
    c = theme.COLORS
    d = int(0.25 * g)
    cv.create_line(x - d, y - d, x + d, y + d, fill=c["component"], width=1, tags=tag)
    cv.create_line(x - d, y + d, x + d, y - d, fill=c["component"], width=1, tags=tag)


def _push_actuator(cv, cx, cy, g, tag):
    """Atuador de botoeira simples: haste + cabeça retangular à esquerda."""
    c = theme.COLORS
    cv.create_line(cx - int(0.3 * g), cy, cx - int(1.0 * g), cy,
                   fill=c["component"], width=2, tags=tag)
    cv.create_rectangle(cx - int(1.0 * g), cy - int(0.5 * g),
                        cx - int(0.7 * g), cy + int(0.5 * g),
                        fill=c["contact"], outline=c["component"], width=1, tags=tag)


def _mushroom_actuator(cv, cx, cy, g, tag, pressed):
    """Atuador de botoeira de emergência (cogumelo, à esquerda)."""
    c = theme.COLORS
    fill = c["pressed"] if pressed else c["contact"]
    cv.create_line(cx - int(0.6 * g), cy, cx - int(1.2 * g), cy,
                   fill=c["component"], width=2, tags=tag)
    cv.create_oval(cx - int(1.8 * g), cy - int(0.7 * g),
                   cx - int(0.8 * g), cy + int(0.7 * g),
                   fill=fill, outline=c["component"], width=2, tags=tag)


def _thermal_flag(cv, cx, cy, g, tag):
    """Retângulo que indica disparo térmico, à direita do contato NF."""
    c = theme.COLORS
    cv.create_rectangle(cx + int(0.3 * g), cy - int(1.6 * g),
                        cx + int(1.0 * g), cy - int(0.6 * g),
                        fill=c["contact"], outline=c["component"], width=1, tags=tag)


# ====================================================================== #
# Fonte de alimentação (barramentos / linhas contínuas)
# ====================================================================== #
SOURCE_CONFIGS = {
    "mono_fn": {
        "label": "Monofásica (F + N)",
        "terminals": [("L", "phase"), ("N", "neutral")],
    },
    "mono_fn_pe": {
        "label": "Monofásica (F + N + PE)",
        "terminals": [("L", "phase"), ("N", "neutral"), ("PE", "earth")],
    },
    "tri_rst": {
        "label": "Trifásica (R + S + T)",
        "terminals": [("R", "phase"), ("S", "phase"), ("T", "phase")],
    },
    "tri_rstn": {
        "label": "Trifásica (R + S + T + N)",
        "terminals": [("R", "phase"), ("S", "phase"), ("T", "phase"), ("N", "neutral")],
    },
    "tri_rstn_pe": {
        "label": "Trifásica (R + S + T + N + PE)",
        "terminals": [("R", "phase"), ("S", "phase"), ("T", "phase"), ("N", "neutral"), ("PE", "earth")],
    },
}


class Source(Component):
    """Barramento de alimentação: linhas contínuas (uma por condutor)."""

    type_key = "source"
    is_source = True
    terminals_spec = []

    def __init__(self, comp_id, x, y, config="mono_fn_pe"):
        if config not in SOURCE_CONFIGS:
            config = "mono_fn_pe"
        self.config = config
        cfg = SOURCE_CONFIGS[config]
        n = len(cfg["terminals"])
        specs = []
        for i, (name, kind) in enumerate(cfg["terminals"]):
            dy = 2 * i - (n - 1)
            specs.append((name, -3, dy, kind))
        self.terminals_spec = specs
        self.footprint = (7, (n - 1) * 2 + 2)
        super().__init__(comp_id, x, y, config=config)

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        kind_color = {"phase": c["live"], "neutral": c["neutral"], "earth": c["earth"]}
        n = len(self.terminals)
        for i, t in enumerate(self.terminals):
            y = cy + (2 * i - (n - 1)) * g
            x1 = cx - 3 * g
            x2 = cx + 3 * g
            if sim is not None and sim.term_status(self.id, t.name) == "short":
                color = c["short"]
            else:
                color = kind_color.get(t.kind, c["component"])
            cv.create_line(x1, y, x2, y, fill=color, width=3, tags=tag)
            cv.create_text(cx - 4 * g, y, text=t.name, fill=c["label"],
                           font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)

    def to_dict(self):
        d = super().to_dict()
        d["config"] = self.config
        return d

    @classmethod
    def from_dict(cls, d):
        c = cls(d["id"], d["x"], d["y"], config=d.get("config", "mono_fn_pe"))
        c.name = d.get("name", "")
        c.coil_name = d.get("coil_name", "K1")
        c.rotation = d.get("rotation", 0)
        return c


# ====================================================================== #
# Chaves (botões e contatos) — verticais
# ====================================================================== #
class Switch(Component):
    is_switch = True
    nc = False                 # NF? (contato de abertura)
    actuator = None            # None | "push" | "mushroom"
    footprint = (5, 5)
    terminals_spec = [("t1", 0, -2), ("t2", 0, 1)]

    def conducting_pairs(self, coil_states):
        return [("t1", "t2")] if self.is_closed(coil_states) else []

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        closed = self.visual_closed(sim)
        _contact_v(cv, cx, cy - 2 * g, cy + g, closed, self.nc, sim, g, tag)
        if self.actuator == "push":
            _push_actuator(cv, cx, cy, g, tag)
        elif self.actuator == "mushroom":
            _mushroom_actuator(cv, cx, cy, g, tag, self.pressed)
        cv.create_text(cx + int(1.7 * g), cy, text=self.display_label(),
                       fill=theme.COLORS["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class ButtonNO(Switch):
    type_key = "button_no"
    name_prefix = "S"
    is_button = True
    actuator = "push"

    def is_closed(self, coil_states):
        return self.pressed


class ButtonNC(Switch):
    type_key = "button_nc"
    name_prefix = "S"
    is_button = True
    nc = True
    actuator = "push"

    def is_closed(self, coil_states):
        return not self.pressed


class ContactNO(Switch):
    type_key = "contact_no"
    name_prefix = None

    def is_closed(self, coil_states):
        return coil_states.get(self.coil_name, False)

    def display_label(self):
        return self.coil_name


class ContactNC(Switch):
    type_key = "contact_nc"
    name_prefix = None
    nc = True

    def is_closed(self, coil_states):
        return not coil_states.get(self.coil_name, False)

    def display_label(self):
        return self.coil_name


class Emergency(Switch):
    type_key = "emergency"
    name_prefix = "S"
    nc = True
    actuator = "mushroom"
    is_toggle = True

    def is_closed(self, coil_states):
        return not self.pressed

    def toggle(self):
        self.pressed = not self.pressed


# ====================================================================== #
# Cargas (bobina, sinaleiro, motor)
# ====================================================================== #
class Coil(Component):
    type_key = "coil"
    name_prefix = "K"
    is_load = True
    footprint = (3, 5)
    terminals_spec = [("t1", 0, -2), ("t2", 0, 2)]

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        top, bot = cy - 2 * g, cy + 2 * g
        bx0, bx1 = cx - int(1.2 * g), cx + int(1.2 * g)
        by0, by1 = cy - int(1.1 * g), cy + int(1.1 * g)
        en = self.visual_energized(sim)
        fill = c["coil_on"] if en else c["coil"]

        cv.create_rectangle(bx0, by0, bx1, by1, fill=fill,
                            outline=c["component"], width=2, tags=tag)
        cv.create_text(cx, cy, text=self.name, fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.5)), "bold"), tags=tag)
        cv.create_line(cx, by0, cx, top, fill=c["component"], width=2, tags=tag)
        cv.create_line(cx, by1, cx, bot, fill=c["component"], width=2, tags=tag)
        cv.create_text(cx - int(0.9 * g), top - 4, text="A1", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)
        cv.create_text(cx - int(0.9 * g), bot + 4, text="A2", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)


class Lamp(Component):
    """Sinaleiro (lâmpada de sinalização)."""

    type_key = "lamp"
    name_prefix = "H"
    is_load = True
    footprint = (4, 5)
    terminals_spec = [("t1", 0, -2), ("t2", 0, 2)]

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        top, bot = cy - 2 * g, cy + 2 * g
        r = int(1.1 * g)
        en = self.visual_energized(sim)
        fill = c["lamp_on"] if en else c["contact"]

        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill,
                       outline=c["component"], width=2, tags=tag)
        cv.create_line(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4,
                       fill=c["component"], width=2, tags=tag)
        cv.create_line(cx - r + 4, cy + r - 4, cx + r - 4, cy - r + 4,
                       fill=c["component"], width=2, tags=tag)
        cv.create_line(cx, cy - r, cx, top, fill=c["component"], width=2, tags=tag)
        cv.create_line(cx, cy + r, cx, bot, fill=c["component"], width=2, tags=tag)
        cv.create_text(cx, top - 8, text=self.name, fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class Motor(Component):
    """Motor trifásico (M 3~)."""

    type_key = "motor"
    name_prefix = "M"
    is_load = True
    footprint = (5, 5)
    terminals_spec = [("U1", -1, -2), ("V1", 0, -2), ("W1", 1, -2)]

    def load_energized(self, roots, phase_nets, neutral_nets):
        seen = set()
        for tname in ("U1", "V1", "W1"):
            root = roots.get(tname)
            if root is None:
                continue
            for pname, nets in phase_nets.items():
                if root in nets:
                    seen.add(pname)
                    break
        return len(seen) >= 3

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        r = int(1.3 * g)
        en = self.visual_energized(sim)
        fill = c["motor_on"] if en else c["contact"]

        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill,
                       outline=c["component"], width=2, tags=tag)
        cv.create_text(cx, cy, text="M 3~", fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.4)), "bold"), tags=tag)
        for tname, dx in (("U1", -1), ("V1", 0), ("W1", 1)):
            tx = cx + dx * g
            cv.create_line(tx, cy - r, tx, cy - 2 * g, fill=c["component"],
                           width=2, tags=tag)
        cv.create_text(cx, cy - 2 * g - 8, text=self.name, fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


# ====================================================================== #
# Disjuntores, contator tripolar, relé térmico e borne
# ====================================================================== #
class Breaker(Component):
    """Disjuntor: chave manual normalmente aberta (NA), com marca de disparo."""

    is_toggle = True

    def __init__(self, comp_id, x, y, config=None):
        self.closed = False
        super().__init__(comp_id, x, y, config=config)

    def toggle(self):
        self.closed = not self.closed

    def reset_interaction(self):
        super().reset_interaction()
        self.closed = False


class Breaker1P(Breaker):
    type_key = "breaker_1p"
    name_prefix = "Q"
    footprint = (5, 5)
    terminals_spec = [("t1", 0, -2), ("t2", 0, 1)]

    def conducting_pairs(self, coil_states):
        return [("t1", "t2")] if self.closed else []

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        _breaker_pole_v(cv, cx, cy - 2 * g, cy + g, self.closed, sim, g, tag)
        cv.create_text(cx + int(1.7 * g), cy, text=self.name,
                       fill=theme.COLORS["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class Breaker3P(Breaker):
    type_key = "breaker_3p"
    name_prefix = "Q"
    footprint = (5, 5)
    terminals_spec = [
        ("1", -1, -2), ("2", -1, 1),
        ("3", 0, -2), ("4", 0, 1),
        ("5", 1, -2), ("6", 1, 1),
    ]

    def conducting_pairs(self, coil_states):
        return [("1", "2"), ("3", "4"), ("5", "6")] if self.closed else []

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        for px in (-1, 0, 1):
            _breaker_pole_v(cv, cx + px * g, cy - 2 * g, cy + g,
                            self.closed, sim, g, tag)
        cv.create_line(cx - g, cy + int(1.5 * g), cx + g, cy + int(1.5 * g),
                       fill=c["component"], dash=(2, 3), width=1, tags=tag)
        cv.create_text(cx, cy - int(3.2 * g), text=self.name,
                       fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class Contact3P(Component):
    """Contato tripolar NA do contator (fecha com a bobina)."""

    type_key = "contact_no_3p"
    name_prefix = None
    is_switch = True
    footprint = (5, 5)
    terminals_spec = [
        ("1", -1, -2), ("2", -1, 1),
        ("3", 0, -2), ("4", 0, 1),
        ("5", 1, -2), ("6", 1, 1),
    ]

    def is_closed(self, coil_states):
        return coil_states.get(self.coil_name, False)

    def display_label(self):
        return self.coil_name

    def conducting_pairs(self, coil_states):
        if self.is_closed(coil_states):
            return [("1", "2"), ("3", "4"), ("5", "6")]
        return []

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        closed = self.visual_closed(sim)
        for px in (-1, 0, 1):
            _contact_v(cv, cx + px * g, cy - 2 * g, cy + g, closed, False, sim, g, tag)
        cv.create_line(cx - g, cy + int(1.5 * g), cx + g, cy + int(1.5 * g),
                       fill=c["component"], dash=(2, 3), width=1, tags=tag)
        cv.create_text(cx, cy - int(3.2 * g), text=self.coil_name,
                       fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class MotorBreaker(Breaker):
    """Disjuntor motor: disjuntor tripolar + contato NF 95-96 com flag térmico."""

    type_key = "motor_breaker"
    name_prefix = "Q"
    footprint = (5, 7)
    terminals_spec = [
        ("1", -1, -2), ("2", -1, 1),
        ("3", 0, -2), ("4", 0, 1),
        ("5", 1, -2), ("6", 1, 1),
        ("95", 0, 2), ("96", 0, 3),
    ]

    def conducting_pairs(self, coil_states):
        if self.closed:
            return [("1", "2"), ("3", "4"), ("5", "6"), ("95", "96")]
        return []

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        for px in (-1, 0, 1):
            _breaker_pole_v(cv, cx + px * g, cy - 2 * g, cy + g,
                            self.closed, sim, g, tag)
        _contact_v(cv, cx, cy + 2 * g, cy + 3 * g, self.closed, True, sim, g, tag)
        _thermal_flag(cv, cx, cy + 2 * g, g, tag)
        cv.create_text(cx - int(1.6 * g), cy + 2.5 * g, text="95", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)
        cv.create_text(cx + int(1.6 * g), cy + 3 * g, text="96", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)
        cv.create_text(cx, cy - int(3.2 * g), text=self.name,
                       fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class Thermal(Component):
    """Relé térmico: polos de potência (aquecedores) + contato NF 95-96."""

    type_key = "thermal"
    name_prefix = "F"
    is_toggle = True
    footprint = (5, 7)
    terminals_spec = [
        ("1", -1, -2), ("2", -1, 1),
        ("3", 0, -2), ("4", 0, 1),
        ("5", 1, -2), ("6", 1, 1),
        ("95", 0, 2), ("96", 0, 3),
    ]

    def __init__(self, comp_id, x, y, config=None):
        self.tripped = False
        super().__init__(comp_id, x, y, config=config)

    def toggle(self):
        self.tripped = not self.tripped

    def reset_interaction(self):
        super().reset_interaction()
        self.tripped = False

    def conducting_pairs(self, coil_states):
        pairs = [("1", "2"), ("3", "4"), ("5", "6")]
        if not self.tripped:
            pairs.append(("95", "96"))
        return pairs

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        for px, term_in in ((-1, "1"), (0, "3"), (1, "5")):
            _heater_line(cv, cx + px * g, cy - 2 * g, cy + g, g, tag,
                         sim, self.id, term_in)
        _contact_v(cv, cx, cy + 2 * g, cy + 3 * g, not self.tripped, True, sim, g, tag)
        _thermal_flag(cv, cx, cy + 2 * g, g, tag)
        cv.create_text(cx - int(1.6 * g), cy + 2.5 * g, text="95", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)
        cv.create_text(cx + int(1.6 * g), cy + 3 * g, text="96", fill=c["label"],
                       font=("Helvetica", 7), tags=tag)
        cv.create_text(cx, cy - int(3.2 * g), text=self.name,
                       fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


class TerminalBlock(Component):
    """Borne: ponto de passagem (sempre condutor)."""

    type_key = "terminal"
    name_prefix = "X"
    footprint = (4, 5)
    terminals_spec = [("t1", 0, -1.5), ("t2", 0, 1.5)]

    def conducting_pairs(self, coil_states):
        return [("t1", "t2")]

    def draw_symbol(self, cv, cx, cy, sim, g, tag):
        c = theme.COLORS
        top, bot = cy - int(1.5 * g), cy + int(1.5 * g)
        color = c["component"]
        if sim is not None:
            color = theme.wire_color(sim.term_status(self.id, "t1"))
        cv.create_line(cx, top, cx, cy - int(0.4 * g), fill=color, width=2, tags=tag)
        cv.create_line(cx, cy + int(0.4 * g), cx, bot, fill=color, width=2, tags=tag)
        r = int(0.4 * g)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=c["contact"], outline=c["component"], width=2, tags=tag)
        cv.create_text(cx + int(1.7 * g), cy, text=self.name, fill=c["label"],
                       font=("Helvetica", max(7, int(g * 0.45)), "bold"), tags=tag)


# ====================================================================== #
# Registro / fábrica
# ====================================================================== #
COMPONENT_TYPES = {
    "source": Source,
    "button_no": ButtonNO,
    "button_nc": ButtonNC,
    "coil": Coil,
    "contact_no": ContactNO,
    "contact_nc": ContactNC,
    "lamp": Lamp,
    "motor": Motor,
    "breaker_1p": Breaker1P,
    "breaker_3p": Breaker3P,
    "motor_breaker": MotorBreaker,
    "thermal": Thermal,
    "terminal": TerminalBlock,
    "emergency": Emergency,
    "contact_no_3p": Contact3P,
}


def create_component(type_key, comp_id, x, y, config=None):
    return COMPONENT_TYPES[type_key](comp_id, x, y, config=config)


def component_from_dict(d):
    cls = COMPONENT_TYPES[d["type"]]
    return cls.from_dict(d)
