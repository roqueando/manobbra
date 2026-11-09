"""Circuito: coleção de componentes e ligações, com persistência JSON."""

from .components import create_component, component_from_dict, GRID


def _norm_endpoint(e):
    """Normaliza extremidade de fio para (comp_id, term_name, anchor)."""
    if len(e) == 2:
        return (e[0], e[1], None)
    return (e[0], e[1], e[2])


class Wire:
    """Ligação elétrica entre dois terminais.

    `a` e `b` são tuplas (component_id, terminal_name). `anchor_a`/`anchor_b`
    são pontos opcionais (dx, dy em células, relativos ao centro do componente)
    que permitem "puxar" o fio de um ponto qualquer do barramento.
    """

    def __init__(self, wire_id, a_comp, a_term, b_comp, b_term,
                 anchor_a=None, anchor_b=None):
        self.id = wire_id
        self.a = (a_comp, a_term)
        self.b = (b_comp, b_term)
        self.anchor_a = anchor_a
        self.anchor_b = anchor_b

    def has_terminal(self, comp_id, tname):
        return (comp_id, tname) in (self.a, self.b)

    def touches_component(self, comp_id):
        return self.a[0] == comp_id or self.b[0] == comp_id


class Circuit:
    def __init__(self):
        self.components = {}
        self.wires = []
        self._next_id = 1
        self._counters = {}
        self.last_coil_name = "K1"

    # ------------------------------------------------------------------ #
    # Mutação
    # ------------------------------------------------------------------ #
    def clear(self):
        self.components = {}
        self.wires = []
        self._next_id = 1
        self._counters = {}
        self.last_coil_name = "K1"

    def new_id(self):
        i = self._next_id
        self._next_id += 1
        return i

    def next_name(self, prefix):
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}{self._counters[prefix]}"

    def add_component(self, type_key, x, y, config=None):
        comp = create_component(type_key, self.new_id(), x, y, config=config)
        if comp.name_prefix:
            comp.name = self.next_name(comp.name_prefix)
            if type_key == "coil":
                self.last_coil_name = comp.name
        if type_key in ("contact_no", "contact_nc"):
            # o contato pertence ao contator mais recente
            comp.coil_name = self.last_coil_name
        self.components[comp.id] = comp
        return comp

    def remove_component(self, comp_id):
        self.components.pop(comp_id, None)
        self.wires = [w for w in self.wires if not w.touches_component(comp_id)]

    def add_wire(self, a, b):
        """a e b: (component_id, terminal_name[, anchor]) — 2 ou 3 itens."""
        a = _norm_endpoint(a)
        b = _norm_endpoint(b)
        a_comp, a_term, a_anchor = a
        b_comp, b_term, b_anchor = b
        if (a_comp, a_term) == (b_comp, b_term):
            return None
        key = {(a_comp, a_term), (b_comp, b_term)}
        for w in self.wires:
            if {w.a, w.b} == key:
                return None  # já existe
        w = Wire(self.new_id(), a_comp, a_term, b_comp, b_term,
                 anchor_a=a_anchor, anchor_b=b_anchor)
        self.wires.append(w)
        return w

    def remove_wire(self, wire_id):
        self.wires = [w for w in self.wires if w.id != wire_id]

    # ------------------------------------------------------------------ #
    # Consulta
    # ------------------------------------------------------------------ #
    def get_component(self, comp_id):
        return self.components.get(comp_id)

    def terminal_position(self, comp_id, tname, grid=GRID):
        comp = self.components.get(comp_id)
        if comp is None:
            return None
        return comp.term_px(tname, grid)

    def endpoint_position(self, comp_id, tname, anchor=None, grid=GRID):
        """Posição (px) de uma extremidade de fio (terminal ou âncora)."""
        comp = self.components.get(comp_id)
        if comp is None:
            return None
        if anchor is None:
            return comp.term_px(tname, grid)
        return comp.anchor_px(anchor[0], anchor[1], grid)

    # ------------------------------------------------------------------ #
    # Persistência
    # ------------------------------------------------------------------ #
    def to_dict(self):
        return {
            "components": [c.to_dict() for c in self.components.values()],
            "wires": [
                {
                    "a": list(w.a),
                    "b": list(w.b),
                    "anchor_a": list(w.anchor_a) if w.anchor_a else None,
                    "anchor_b": list(w.anchor_b) if w.anchor_b else None,
                }
                for w in self.wires
            ],
            "next_id": self._next_id,
            "counters": self._counters,
            "last_coil_name": self.last_coil_name,
        }

    def from_dict(self, d):
        self.clear()
        self._next_id = d.get("next_id", 1)
        self._counters = dict(d.get("counters", {}))
        self.last_coil_name = d.get("last_coil_name", "K1")
        for cd in d.get("components", []):
            comp = component_from_dict(cd)
            self.components[comp.id] = comp
        for wd in d.get("wires", []):
            a = tuple(wd["a"])
            b = tuple(wd["b"])
            aa = tuple(wd["anchor_a"]) if wd.get("anchor_a") else None
            ab = tuple(wd["anchor_b"]) if wd.get("anchor_b") else None
            w = Wire(self.new_id(), a[0], a[1], b[0], b[1],
                     anchor_a=aa, anchor_b=ab)
            self.wires.append(w)
