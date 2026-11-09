"""Testes do motor de simulação (sem GUI)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.model.circuit import Circuit
from app.model.simulator import Simulator
from app.model.examples import build_direct_start


def _by_type(circuit, type_key):
    return [c for c in circuit.components.values() if c.type_key == type_key]


def test_partida_direta_com_selo():
    c = Circuit()
    build_direct_start(c)
    sim = Simulator()
    mem = {}

    coil = _by_type(c, "coil")[0]
    start = _by_type(c, "button_no")[0]
    stop = _by_type(c, "emergency")[0]

    sim.run(c, mem)
    assert coil.sim_energized is False

    start.pressed = True
    sim.run(c, mem)
    assert coil.sim_energized is True

    start.pressed = False
    sim.run(c, mem)
    assert coil.sim_energized is True, "selo deve manter a bobina energizada"

    stop.toggle()  # pressiona a emergência (trava, NF abre)
    sim.run(c, mem)
    assert coil.sim_energized is False

    stop.toggle()  # desarma a emergência
    sim.run(c, mem)
    assert coil.sim_energized is False


def test_cargas_energizadas():
    c = Circuit()
    build_direct_start(c)
    sim = Simulator()
    mem = {}

    breaker = _by_type(c, "breaker_3p")[0]
    breaker.toggle()  # fecha o disjuntor NA

    start = _by_type(c, "button_no")[0]
    start.pressed = True
    sim.run(c, mem)

    lamp = _by_type(c, "lamp")[0]
    motor = _by_type(c, "motor")[0]
    assert lamp.sim_energized is True
    assert motor.sim_energized is True

    stop = _by_type(c, "emergency")[0]
    stop.toggle()
    sim.run(c, mem)
    assert lamp.sim_energized is False
    assert motor.sim_energized is False


def test_curto_circuito_detectado():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    c.add_wire((src.id, "L"), (src.id, "N"))
    sim = Simulator()
    state = sim.run(c, {})
    assert state.short is True


def test_fonte_monofasica_fase_neutro_terra():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn_pe")  # L, N, PE
    coil_ln = c.add_component("coil", 6, 2)
    coil_lpe = c.add_component("coil", 6, 5)
    coil_npe = c.add_component("coil", 6, 8)

    c.add_wire((src.id, "L"), (coil_ln.id, "t1"))
    c.add_wire((coil_ln.id, "t2"), (src.id, "N"))
    c.add_wire((src.id, "L"), (coil_lpe.id, "t1"))
    c.add_wire((coil_lpe.id, "t2"), (src.id, "PE"))
    c.add_wire((src.id, "N"), (coil_npe.id, "t1"))
    c.add_wire((coil_npe.id, "t2"), (src.id, "PE"))

    sim = Simulator()
    state = sim.run(c, {})
    assert coil_ln.sim_energized is True, "F+N deve energizar"
    assert coil_lpe.sim_energized is False, "F+PE não deve energizar"
    assert coil_npe.sim_energized is False, "N+PE não deve energizar"
    assert state.short is False


def test_fonte_trifasica_fase_fase():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rst")  # R, S, T
    coil_rs = c.add_component("coil", 6, 2)
    c.add_wire((src.id, "R"), (coil_rs.id, "t1"))
    c.add_wire((coil_rs.id, "t2"), (src.id, "S"))

    sim = Simulator()
    state = sim.run(c, {})
    assert coil_rs.sim_energized is True, "fase-fase (R-S) deve energizar"
    assert state.short is False


def test_mesma_fase_nao_energiza():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rst")
    coil = c.add_component("coil", 6, 2)
    c.add_wire((src.id, "R"), (coil.id, "t1"))
    c.add_wire((coil.id, "t2"), (src.id, "R"))

    sim = Simulator()
    state = sim.run(c, {})
    assert coil.sim_energized is False, "mesma fase (0V) não deve energizar"
    assert state.short is False


def test_curto_fase_neutro_trifasico():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rstn")
    c.add_wire((src.id, "R"), (src.id, "N"))
    sim = Simulator()
    state = sim.run(c, {})
    assert state.short is True


def test_disjuntor_aberto():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    q = c.add_component("breaker_1p", 6, 2)
    coil = c.add_component("coil", 10, 2)
    c.add_wire((src.id, "L"), (q.id, "t1"))
    c.add_wire((q.id, "t2"), (coil.id, "t1"))
    c.add_wire((coil.id, "t2"), (src.id, "N"))

    sim = Simulator()
    sim.run(c, {})
    assert coil.sim_energized is False, "disjuntor NA (aberto) não deve energizar"
    q.toggle()  # fecha
    sim.run(c, {})
    assert coil.sim_energized is True, "disjuntor fechado deve energizar"
    q.toggle()  # abre de novo
    sim.run(c, {})
    assert coil.sim_energized is False


def test_disjuntor_tripolar():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rst")
    q = c.add_component("breaker_3p", 6, 2)
    coil = c.add_component("coil", 10, 2)
    c.add_wire((src.id, "R"), (q.id, "1"))
    c.add_wire((q.id, "2"), (coil.id, "t1"))
    c.add_wire((coil.id, "t2"), (src.id, "S"))

    sim = Simulator()
    sim.run(c, {})
    assert coil.sim_energized is False, "disjuntor NA não energiza"
    q.toggle()
    sim.run(c, {})
    assert coil.sim_energized is True
    q.toggle()
    sim.run(c, {})
    assert coil.sim_energized is False


def test_rele_termico():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    f = c.add_component("thermal", 6, 2)
    coil_power = c.add_component("coil", 10, 2)
    coil_aux = c.add_component("coil", 10, 5)
    # potência: L -> 1 -> 2 -> bobina -> N
    c.add_wire((src.id, "L"), (f.id, "1"))
    c.add_wire((f.id, "2"), (coil_power.id, "t1"))
    c.add_wire((coil_power.id, "t2"), (src.id, "N"))
    # comando: L -> 95 -> 96 -> bobina -> N
    c.add_wire((src.id, "L"), (f.id, "95"))
    c.add_wire((f.id, "96"), (coil_aux.id, "t1"))
    c.add_wire((coil_aux.id, "t2"), (src.id, "N"))

    sim = Simulator()
    sim.run(c, {})
    assert coil_power.sim_energized is True
    assert coil_aux.sim_energized is True
    f.toggle()  # trip: abre 95-96; potência continua condutora
    sim.run(c, {})
    assert coil_power.sim_energized is True
    assert coil_aux.sim_energized is False


def test_botoeira_emergencia():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    s = c.add_component("emergency", 6, 2)
    coil = c.add_component("coil", 10, 2)
    c.add_wire((src.id, "L"), (s.id, "t1"))
    c.add_wire((s.id, "t2"), (coil.id, "t1"))
    c.add_wire((coil.id, "t2"), (src.id, "N"))

    sim = Simulator()
    sim.run(c, {})
    assert coil.sim_energized is True, "emergência NF fechada deve energizar"
    s.toggle()  # pressiona (trava)
    sim.run(c, {})
    assert coil.sim_energized is False
    s.toggle()  # desarma
    sim.run(c, {})
    assert coil.sim_energized is True


def test_borne():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    x = c.add_component("terminal", 6, 2)
    coil = c.add_component("coil", 10, 2)
    c.add_wire((src.id, "L"), (x.id, "t1"))
    c.add_wire((x.id, "t2"), (coil.id, "t1"))
    c.add_wire((coil.id, "t2"), (src.id, "N"))

    sim = Simulator()
    sim.run(c, {})
    assert coil.sim_energized is True, "borne é condutor (passagem)"


def test_rotacao_terminal():
    c = Circuit()
    coil = c.add_component("coil", 5, 5)
    assert coil.term_px("t1") == (100, 60)      # (0, -2) células
    coil.rotation = 90
    assert coil.term_px("t1") == (60, 100)      # (0, -2) -> (-2, 0)
    coil.rotation = 180
    assert coil.term_px("t1") == (100, 140)     # -> (0, 2)


def test_fio_ancorado_no_barramento():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    coil = c.add_component("coil", 6, 2)
    # puxa o fio de um ponto do barramento L (âncora), não do terminal exato
    c.add_wire((src.id, "L", (1, -1)), (coil.id, "t1", None))
    c.add_wire((coil.id, "t2", None), (src.id, "N", None))
    sim = Simulator()
    sim.run(c, {})
    assert coil.sim_energized is True


def test_endpoint_ancorado():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="mono_fn")
    assert c.endpoint_position(src.id, "L", (1, -1)) == (60, 20)


def test_motor_trifasico():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rst")
    m = c.add_component("motor", 8, 2)
    c.add_wire((src.id, "R"), (m.id, "U1"))
    c.add_wire((src.id, "S"), (m.id, "V1"))
    c.add_wire((src.id, "T"), (m.id, "W1"))
    sim = Simulator()
    state = sim.run(c, {})
    assert m.sim_energized is True, "motor 3~ com R/S/T deve energizar"
    assert state.short is False


def test_motor_trifasico_fase_insuficiente():
    c = Circuit()
    src = c.add_component("source", 2, 2, config="tri_rst")
    m = c.add_component("motor", 8, 2)
    c.add_wire((src.id, "R"), (m.id, "U1"))
    c.add_wire((src.id, "S"), (m.id, "V1"))
    c.add_wire((src.id, "S"), (m.id, "W1"))  # só 2 fases distintas
    sim = Simulator()
    sim.run(c, {})
    assert m.sim_energized is False, "motor 3~ precisa de 3 fases distintas"


if __name__ == "__main__":
    test_partida_direta_com_selo()
    test_cargas_energizadas()
    test_curto_circuito_detectado()
    test_fonte_monofasica_fase_neutro_terra()
    test_fonte_trifasica_fase_fase()
    test_mesma_fase_nao_energiza()
    test_curto_fase_neutro_trifasico()
    test_disjuntor_aberto()
    test_disjuntor_tripolar()
    test_rele_termico()
    test_botoeira_emergencia()
    test_borne()
    test_rotacao_terminal()
    test_fio_ancorado_no_barramento()
    test_endpoint_ancorado()
    test_motor_trifasico()
    test_motor_trifasico_fase_insuficiente()
    print("Todos os testes passaram ✓")
