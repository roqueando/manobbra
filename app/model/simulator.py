"""Motor de simulação elétrica (lógica de comandos).

Ideia central: modelamos a parte de *comando* do circuito (que é o foco de um
simulador de comandos elétricos). Cada terminal é um nó; fios e contatos
fechados são condutores ideais (unem nós numa mesma "rede" equipotencial).
Cargas (bobina, lâmpada, motor) são os elementos medidos: ficam energizadas
quando seus terminais estão entre potenciais diferentes que formam uma
alimentação válida (fase↔neutro ou fase↔fase). O terra (PE) nunca alimenta.

O estado das bobinas tem *memória* entre passos (passado em `coil_memory`),
o que permite simular auto-retenção ("selo") e outros travamentos.
"""


class UnionFind:
    def __init__(self):
        self.parent = {}

    def make(self):
        i = len(self.parent)
        self.parent[i] = i
        return i

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class SimState:
    """Resultado de uma simulação, usado também para colorir a tela."""

    def __init__(self):
        self.terminal_net = {}   # (comp_id, term_name) -> raiz da rede
        self.phase_nets = {}     # nome_da_fase (R/S/T/L) -> set(raízes)
        self.neutral_nets = set()
        self.earth_nets = set()
        self.short = False

    def net_status(self, root):
        if root is None:
            return "float"
        phases = [p for p, nets in self.phase_nets.items() if root in nets]
        has_neutral = root in self.neutral_nets
        has_earth = root in self.earth_nets
        distinct = len(phases) + (1 if has_neutral else 0) + (1 if has_earth else 0)
        if distinct >= 2:
            return "short"
        if phases:
            return "live"
        if has_neutral:
            return "neutral"
        if has_earth:
            return "earth"
        return "float"

    def term_status(self, comp_id, tname):
        return self.net_status(self.terminal_net.get((comp_id, tname)))


class Simulator:
    MAX_ITER = 30

    def run(self, circuit, coil_memory=None):
        if coil_memory is None:
            coil_memory = {}
        coil = dict(coil_memory)
        comps = list(circuit.components.values())

        uf = None
        node = {}
        phase_nets = {}
        neutral_nets = set()
        earth_nets = set()

        for _ in range(self.MAX_ITER):
            changed = False
            uf = UnionFind()
            node = {}

            def n(cid, tname):
                key = (cid, tname)
                if key not in node:
                    node[key] = uf.make()
                return node[key]

            # 1) fios são condutores ideais
            for w in circuit.wires:
                uf.union(n(w.a[0], w.a[1]), n(w.b[0], w.b[1]))

            # 2) contatos/polos fechados também
            for comp in comps:
                for ta, tb in comp.conducting_pairs(coil):
                    uf.union(n(comp.id, ta), n(comp.id, tb))

            # 3) classifica as redes ligadas a cada potencial da fonte
            phase_nets = {}
            neutral_nets = set()
            earth_nets = set()
            for comp in comps:
                if comp.is_source:
                    for t in comp.terminals:
                        root = uf.find(n(comp.id, t.name))
                        if t.kind == "phase":
                            phase_nets.setdefault(t.phase_name, set()).add(root)
                        elif t.kind == "neutral":
                            neutral_nets.add(root)
                        elif t.kind == "earth":
                            earth_nets.add(root)

            # 4) energiza cargas e propaga o estado das bobinas
            for comp in comps:
                if comp.is_load:
                    roots = {t.name: uf.find(n(comp.id, t.name)) for t in comp.terminals}
                    en = comp.load_energized(roots, phase_nets, neutral_nets)
                    comp.sim_energized = en
                    if comp.type_key == "coil":
                        if coil.get(comp.name) != en:
                            coil[comp.name] = en
                            changed = True

            if not changed:
                break

        # fixa o estado final das chaves para o desenho
        for comp in comps:
            if comp.is_switch:
                comp.sim_closed = comp.is_closed(coil)

        state = SimState()
        state.terminal_net = {k: uf.find(v) for k, v in node.items()}
        state.phase_nets = phase_nets
        state.neutral_nets = neutral_nets
        state.earth_nets = earth_nets
        state.short = any(
            state.net_status(root) == "short"
            for root in set(state.terminal_net.values())
        )

        coil_memory.clear()
        coil_memory.update(coil)
        return state
