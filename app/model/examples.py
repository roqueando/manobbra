"""Circuitos de exemplo prontos para carregar."""


def build_direct_start(circuit):
    """Partida direta trifásica com selo + sinaleiro.

    Potência:  R/S/T -> Q1 (disjuntor tripolar) -> KM1 (contator 3P)
               -> F1 (relé térmico) -> M1 (motor 3~).
    Comando:   R -> S0 (emergência NF) -> S1 (partida NA) -> K1 -> N,
               com selo KM1 em paralelo a S1 e sinaleiro H1 em paralelo a K1.
    """
    src = circuit.add_component("source", 2, 4, config="tri_rstn")
    k1 = circuit.add_component("coil", 13, 18)         # bobina K1
    km1 = circuit.add_component("contact_no_3p", 8, 7)  # contator de potência
    selo = circuit.add_component("contact_no", 16, 13)  # selo (1 polo)
    q1 = circuit.add_component("breaker_3p", 8, 3)      # disjuntor tripolar
    f1 = circuit.add_component("thermal", 8, 11)        # relé térmico
    m1 = circuit.add_component("motor", 8, 16)          # motor trifásico
    s0 = circuit.add_component("emergency", 13, 9)      # emergência
    s1 = circuit.add_component("button_no", 13, 13)     # partida
    h1 = circuit.add_component("lamp", 16, 18)          # sinaleiro

    def w(c1, t1, c2, t2):
        circuit.add_wire((c1.id, t1), (c2.id, t2))

    def wa(c1, t1, anc1, c2, t2, anc2=None):
        circuit.add_wire((c1.id, t1, anc1), (c2.id, t2, anc2))

    # potência
    wa(src, "R", (3, -3), q1, "1")
    wa(src, "S", (3, -1), q1, "3")
    wa(src, "T", (3, 1), q1, "5")
    w(q1, "2", km1, "1")
    w(q1, "4", km1, "3")
    w(q1, "6", km1, "5")
    w(km1, "2", f1, "1")
    w(km1, "4", f1, "3")
    w(km1, "6", f1, "5")
    w(f1, "2", m1, "U1")
    w(f1, "4", m1, "V1")
    w(f1, "6", m1, "W1")

    # comando
    wa(src, "R", (3, -3), s0, "t1")
    w(s0, "t2", s1, "t1")
    w(s0, "t2", selo, "t1")
    w(s1, "t2", selo, "t2")
    w(s1, "t2", k1, "t1")
    w(h1, "t1", k1, "t1")
    w(h1, "t2", k1, "t2")
    wa(k1, "t2", None, src, "N", (3, 3))

    return circuit
