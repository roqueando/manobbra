"""Janela principal da aplicação."""

import json
import tkinter as tk
from tkinter import filedialog, messagebox

from ..model.circuit import Circuit
from ..model.simulator import Simulator
from ..model.examples import build_direct_start
from .canvas import SchematicCanvas
from .icons import ComponentIconButton
from .widgets import ScrollableFrame

# Catálogo da biblioteca: (tipo, configuração, rótulo).
# A configuração só se aplica às fontes (número de condutores).
CATALOG = [
    ("source", "mono_fn", "Fonte Monofásica (F+N)"),
    ("source", "mono_fn_pe", "Fonte Monofásica (F+N+PE)"),
    ("source", "tri_rst", "Fonte Trifásica (R+S+T)"),
    ("source", "tri_rstn", "Fonte Trifásica (R+S+T+N)"),
    ("source", "tri_rstn_pe", "Fonte Trifásica (R+S+T+N+PE)"),
    ("breaker_1p", None, "Disjuntor Monopolar"),
    ("breaker_3p", None, "Disjuntor Tripolar"),
    ("motor_breaker", None, "Disjuntor Motor"),
    ("thermal", None, "Relé Térmico"),
    ("coil", None, "Bobina (K)"),
    ("contact_no", None, "Contato NA (KM)"),
    ("contact_nc", None, "Contato NF (KM)"),
    ("contact_no_3p", None, "Contator 3P (KM)"),
    ("button_no", None, "Botoeira Simples NA"),
    ("button_nc", None, "Botoeira Simples NF"),
    ("emergency", None, "Botoeira de Emergência"),
    ("lamp", None, "Sinaleiro (H)"),
    ("motor", None, "Motor Trifásico (M 3~)"),
    ("terminal", None, "Borne (X)"),
]

CATALOG_LABEL = {(t, cfg): label for (t, cfg, label) in CATALOG}


class App:
    def __init__(self, root):
        self.root = root
        self.circuit = Circuit()
        self.simulator = Simulator()
        self.coil_memory = {}
        self.mode = "edit"
        self.pending_type = None
        self.pending_config = None
        self.sim_state = None
        self.current_file = None
        self.palette_buttons = {}

        root.title("EletroComando — Simulador de Comandos Elétricos")
        root.geometry("1280x800")

        self._build_menu()
        self._build_toolbar()
        self._build_layout()

        self.canvas.redraw()
        self.update_status()

    # ------------------------------------------------------------------ #
    # Construção da interface
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Novo", accelerator="Cmd+N", command=self.new_circuit)
        file_menu.add_command(label="Abrir…", accelerator="Cmd+O", command=self.open_circuit)
        file_menu.add_command(label="Salvar", accelerator="Cmd+S", command=self.save_circuit)
        file_menu.add_command(label="Salvar como…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.destroy)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Aumentar zoom (Ctrl+)", command=self.zoom_in)
        view_menu.add_command(label="Diminuir zoom (Ctrl-)", command=self.zoom_out)
        view_menu.add_command(label="Zoom 100%", command=self.zoom_reset)
        view_menu.add_separator()
        view_menu.add_command(label="Biblioteca de componentes", command=self.open_component_library)
        menubar.add_cascade(label="Exibir", menu=view_menu)

        ex_menu = tk.Menu(menubar, tearoff=0)
        ex_menu.add_command(label="Partida direta com selo", command=self.load_demo)
        menubar.add_cascade(label="Exemplos", menu=ex_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Sobre", command=self.show_about)
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        self.root.config(menu=menubar)

    def _button(self, parent, text, command, **kw):
        b = tk.Button(parent, text=text, command=command, **kw)
        b.pack(side="left", padx=2)
        return b

    def _separator(self, parent):
        tk.Frame(parent, width=10).pack(side="left")

    def _build_toolbar(self):
        bar = tk.Frame(self.root, padx=6, pady=4)
        bar.pack(side="top", fill="x")

        self.btn_select = self._button(bar, "Selecionar", lambda: self.set_tool("select"))
        self.btn_pan = self._button(bar, "Mover (pan)", lambda: self.set_tool("pan"))
        self._separator(bar)

        self.btn_edit = self._button(bar, "Editar", lambda: self.set_mode("edit"))
        self.btn_sim = self._button(bar, "Simular", lambda: self.set_mode("simulate"))
        self._separator(bar)

        self._button(bar, "−", self.zoom_out)
        self._button(bar, "+", self.zoom_in)
        self._button(bar, "100%", self.zoom_reset)
        self._button(bar, "Girar 90°", self.rotate_selected)
        self._separator(bar)

        self._button(bar, "Novo", self.new_circuit)
        self._button(bar, "Abrir", self.open_circuit)
        self._button(bar, "Salvar", self.save_circuit)
        self._separator(bar)

        self._button(bar, "Biblioteca…", self.open_component_library)
        self._button(bar, "Exemplo: Partida direta", self.load_demo)

        self._update_mode_buttons()

    def _build_layout(self):
        # barra de status embaixo (antes da área principal, para reservar espaço)
        self.status = tk.Label(self.root, text="", anchor="w", padx=8, pady=3)
        self.status.pack(side="bottom", fill="x")

        # área principal: paleta (esquerda) + esquema (direita)
        main = tk.Frame(self.root)
        main.pack(side="top", fill="both", expand=True)

        palette = tk.Frame(main, width=190)
        palette.pack(side="left", fill="y")
        palette.pack_propagate(False)

        tk.Label(palette, text="Componentes", font=("Helvetica", 12, "bold")).pack(
            pady=(10, 4), padx=8, anchor="w")

        scroll = ScrollableFrame(palette)
        scroll.pack(fill="both", expand=True)

        for type_key, config, label in CATALOG:
            b = ComponentIconButton(
                scroll.inner, type_key, label,
                command=lambda k=type_key, cfg=config: self.select_component(k, cfg),
                icon_size=(88, 64), config=config)
            b.pack(fill="x", padx=8, pady=3)
            self.palette_buttons[(type_key, config)] = b
        scroll.enable_wheel()

        # área do esquema (canvas + scrollbars)
        canvas_area = tk.Frame(main)
        canvas_area.pack(side="left", fill="both", expand=True)

        self.canvas = SchematicCanvas(canvas_area, self)
        hbar = tk.Scrollbar(canvas_area, orient="horizontal", command=self.canvas.xview)
        vbar = tk.Scrollbar(canvas_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        canvas_area.rowconfigure(0, weight=1)
        canvas_area.columnconfigure(0, weight=1)

        # atalhos de teclado
        self.root.bind("<Delete>", lambda e: self.canvas.delete_selection())
        self.root.bind("<BackSpace>", lambda e: self.canvas.delete_selection())
        self.root.bind("<Escape>", lambda e: self.canvas.cancel_action())
        self.root.bind("<Control-s>", lambda e: self.save_circuit())
        self.root.bind("<Control-o>", lambda e: self.open_circuit())
        self.root.bind("<Control-n>", lambda e: self.new_circuit())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        self.root.bind("<Key-r>", lambda e: self.rotate_selected())
        self.root.bind("<Key-R>", lambda e: self.rotate_selected())

        self._update_tool_buttons()
        self._sync_cursor()

    # ------------------------------------------------------------------ #
    # Ferramentas / zoom
    # ------------------------------------------------------------------ #
    def set_tool(self, tool):
        self.canvas.set_tool(tool)
        self._update_tool_buttons()
        self._sync_cursor()
        self.update_status()

    def zoom_in(self):
        self.canvas.zoom(1.25)

    def zoom_out(self):
        self.canvas.zoom(1 / 1.25)

    def zoom_reset(self):
        self.canvas.zoom_reset()

    def rotate_selected(self):
        comp = self.canvas.selected_comp
        if comp is None:
            return
        comp.rotation = (comp.rotation + 90) % 360
        self.on_circuit_changed()
        self.canvas.redraw()
        self.update_status()

    def _update_tool_buttons(self):
        self.btn_select.config(relief="sunken" if self.canvas.tool == "select" else "raised")
        self.btn_pan.config(relief="sunken" if self.canvas.tool == "pan" else "raised")

    def _sync_cursor(self):
        if self.pending_type:
            self.canvas.configure(cursor="crosshair")
        elif self.canvas.tool == "pan":
            self.canvas.configure(cursor="fleur")
        else:
            self.canvas.configure(cursor="")

    # ------------------------------------------------------------------ #
    # Biblioteca de componentes
    # ------------------------------------------------------------------ #
    def open_component_library(self):
        win = tk.Toplevel(self.root)
        win.title("Biblioteca de componentes")
        win.transient(self.root)
        win.geometry("700x520")

        scroll = ScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        for i, (type_key, config, label) in enumerate(CATALOG):
            icon = ComponentIconButton(
                scroll.inner, type_key, label,
                command=lambda k=type_key, cfg=config: self._choose_from_library(k, cfg, win),
                icon_size=(120, 88), config=config)
            icon.grid(row=i // 4, column=i % 4, padx=10, pady=10)
        scroll.enable_wheel()
        tk.Button(win, text="Fechar", command=win.destroy).pack(pady=(0, 12))

    def _choose_from_library(self, type_key, config, win):
        self.select_component(type_key, config)
        win.destroy()

    # ------------------------------------------------------------------ #
    # Modo e seleção
    # ------------------------------------------------------------------ #
    def set_mode(self, mode):
        self.mode = mode
        self.pending_type = None
        self.pending_config = None
        self.sync_palette()
        if mode == "simulate":
            self.canvas.wire_start = None
            self.canvas.wire_cursor = None
            self.canvas.selected_comp = None
            self.canvas.selected_wire = None
            self.canvas._ghost_pos = None
            self.coil_memory = {}
            self.refresh_sim()
        else:
            self.sim_state = None
            for comp in self.circuit.components.values():
                comp.reset_interaction()
            self.canvas.redraw()
        self._update_mode_buttons()
        self._sync_cursor()
        self.update_status()

    def select_component(self, type_key, config=None):
        if self.mode != "edit":
            self.set_mode("edit")
        self.set_tool("select")
        self.pending_type = type_key
        self.pending_config = config
        self.canvas.selected_comp = None
        self.canvas.selected_wire = None
        self.canvas.wire_start = None
        self.canvas.wire_cursor = None
        self.canvas._ghost_pos = None
        self.sync_palette()
        self._sync_cursor()
        self.canvas.redraw()
        self.update_status()

    def clear_pending(self):
        self.pending_type = None
        self.pending_config = None
        self.canvas._ghost_pos = None
        self.sync_palette()
        self._sync_cursor()

    def _update_mode_buttons(self):
        self.btn_edit.config(relief="sunken" if self.mode == "edit" else "raised")
        self.btn_sim.config(relief="sunken" if self.mode == "simulate" else "raised")

    def sync_palette(self):
        for k, b in self.palette_buttons.items():
            b.config(relief="sunken" if k == (self.pending_type, self.pending_config) else "flat")

    # ------------------------------------------------------------------ #
    # Simulação
    # ------------------------------------------------------------------ #
    def refresh_sim(self):
        if self.mode != "simulate":
            return
        self.sim_state = self.simulator.run(self.circuit, self.coil_memory)
        self.canvas.redraw()
        self.update_status()

    def on_circuit_changed(self):
        # toda mudança estrutural invalida a simulação em andamento
        self.sim_state = None
        self.update_status()

    # ------------------------------------------------------------------ #
    # Arquivo
    # ------------------------------------------------------------------ #
    def _confirm_discard(self):
        if not self.circuit.components and not self.circuit.wires:
            return True
        return messagebox.askyesno(
            "Confirmar", "Descartar o circuito atual e continuar?")

    def new_circuit(self):
        if not self._confirm_discard():
            return
        self.circuit.clear()
        self.current_file = None
        self.set_mode("edit")
        self.canvas.redraw()
        self.update_status()

    def load_demo(self):
        if not self._confirm_discard():
            return
        self.circuit.clear()
        build_direct_start(self.circuit)
        self.current_file = None
        self.set_mode("edit")
        self.canvas.redraw()
        self.update_status()

    def save_circuit(self):
        if self.current_file:
            self._write_file(self.current_file)
        else:
            self.save_as()

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Circuito EletroComando", "*.json"), ("Todos", "*.*")],
            initialfile="circuito.json")
        if path:
            self._write_file(path)

    def _write_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.circuit.to_dict(), f, ensure_ascii=False, indent=2)
        self.current_file = path
        self.update_status()

    def open_circuit(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            filetypes=[("Circuito EletroComando", "*.json"), ("Todos", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.circuit.from_dict(data)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", f"Não foi possível abrir o arquivo:\n{exc}")
            return
        self.current_file = path
        self.set_mode("edit")
        self.canvas.redraw()
        self.update_status()

    def show_about(self):
        messagebox.showinfo(
            "Sobre",
            "EletroComando\n"
            "Simulador de comandos elétricos (MVP)\n"
            "Inspirado em CADe SIMU e QElectroTech.\n\n"
            "Como usar:\n"
            "  • Escolha um componente na biblioteca e clique na área.\n"
            "  • Clique em um terminal e depois em outro para ligar.\n"
            "  • Ferramentas: Selecionar, Mover (pan) e zoom (roda com Ctrl).\n"
            "  • Em 'Simular', clique e segure os botões (S).\n"
            "  • Delete remove a seleção; botão direito também remove.")

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def update_status(self):
        zoom_pct = int(round(self.canvas.zoom_level * 100))
        parts = [
            f"Modo: {'EDITAR' if self.mode == 'edit' else 'SIMULAR'}",
            f"Componentes: {len(self.circuit.components)}",
            f"Ligações: {len(self.circuit.wires)}",
            f"Zoom: {zoom_pct}%",
        ]
        if self.mode == "edit":
            if self.pending_type:
                parts.append(f"Inserir: {CATALOG_LABEL.get((self.pending_type, self.pending_config), self.pending_type)}")
            elif self.canvas.wire_start:
                parts.append("Clique em outro terminal para ligar (Esc cancela)")
            elif self.canvas.selected_comp:
                parts.append(f"Selecionado: {self.canvas.selected_comp.display_label() or self.canvas.selected_comp.type_key}")
            elif self.canvas.selected_wire:
                parts.append("Ligação selecionada")
        else:
            if self.sim_state and self.sim_state.short:
                parts.append("⚠ CURTO-CIRCUITO detectado")
            else:
                parts.append("Pressione os botões (S) para acionar")
        self.status.config(text="   |   ".join(parts))
