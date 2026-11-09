# EletroComando

Simulador de **comandos elétricos** para desktop, inspirado em
[CADe SIMU](https://cadetransformadores.com/) e
[QElectroTech](https://qelectrotech.org/). MVP em **Python + Tkinter**,
gerenciado com **Poetry**.

Os **símbolos** dos componentes seguem a norma brasileira (IEC 60617 / NBR),
com orientação vertical conforme a biblioteca do **QElectroTech**.

## Como rodar

```bash
poetry install
poetry run eletrocomando          # ou: poetry run python main.py
```

Requer Python 3.8+ (Tkinter já vem junto na instalação padrão).

## O que já funciona (MVP)

- **Área de desenho** com grade e encaixe na grade.
- **Biblioteca de componentes** com **ícones desenhados** (símbolos) para
  escolher cada item — disponível na paleta lateral e no menu
  *Exibir → Biblioteca de componentes*:
  - **Fontes de alimentação** (barramentos em linhas contínuas):
    monofásica (F+N, F+N+PE) e trifásica (R+S+T, R+S+T+N, R+S+T+N+PE)
  - **Disjuntor** Monopolar e Tripolar (NA, com marca de disparo ×)
  - **Disjuntor Motor** (3 polos + contato NF 95-96)
  - **Relé Térmico** (3 polos de potência + contato NF 95-96)
  - **Borne** (ponto de passagem)
  - **Bobina de contator (K)**, **Contato NA/NF** e **Contator 3P (KM)**
  - **Botoeira Simples** NA e NF (pulsador)
  - **Botoeira de Emergência** (cogumelo NF com trava)
  - **Sinaleiro (H)** e **Motor Trifásico (M 3~)**
- **Ligação de fios**: clique em um terminal ou em **qualquer ponto do
  barramento** de força (fase, neutro, terra...) e depois no destino — o fio é
  roteado de forma **ortogonal** (horizontal/vertical).
- **Edição**: inserir, arrastar/mover, **girar 90°** (botão "Girar 90°" ou tecla
  `R`), selecionar, excluir (tecla Delete ou botão direito).
- **Navegação**:
  - ferramenta **Selecionar** (seta) — inserir/mover/ligar;
  - ferramenta **Mover (pan)** — arrastar para deslocar a vista;
  - **zoom** pelos botões `+`/`−`/`100%` ou `Ctrl` + roda do mouse;
  - roda do mouse rola vertical; `Shift` + roda rola horizontal;
  - botão do meio arrasta (pan) em qualquer ferramenta.
- **Simulação lógica** do circuito de comando:
  - propaga os potenciais (fases, neutro e terra) pelos fios e contatos fechados;
  - energiza bobinas, lâmpadas e motores (fase↔neutro e fase↔fase);
  - contatos do contator acompanham o estado da bobina;
  - **auto-retenção ("selo")** com memória de estado;
  - detecção de **curto-circuito**.
- **Salvar / abrir** circuito em JSON.
- **Circuito de exemplo**: partida direta com selo + lâmpada de sinalização.

## Como usar

1. Escolha um componente na biblioteca (paleta à esquerda ou menu *Exibir*)
   e clique na área para inseri-lo.
2. Para ligar: clique no terminal (ou em qualquer ponto do barramento de força)
   e depois no terminal/barramento de destino. (`Esc` cancela; arrastar move;
   `Delete` apaga a seleção; `R` ou o botão "Girar 90°" gira o componente.)
3. Clique em **Simular**:
   - **pulsadores** (botoeiras simples) fecham enquanto pressionados;
   - **dispositivos com trava** (disjuntores, disjuntor motor, relé térmico e
     botoeira de emergência) alternam a cada clique (liga/desliga).
4. Volte para **Editar** para mudar o circuito.

## Estrutura do projeto

```
eletrocomando/
├── main.py                 # ponto de entrada
├── pyproject.toml          # projeto Poetry
├── app/
│   ├── theme.py            # cores dos elementos do esquema
│   ├── model/              # lógica pura (sem tkinter)
│   │   ├── components.py   # símbolos, terminais e estados
│   │   ├── circuit.py      # componentes + fios + JSON
│   │   ├── simulator.py    # motor de simulação
│   │   └── examples.py     # circuito de exemplo
│   └── ui/
│       ├── app.py          # janela, menu, paleta, status
│       ├── canvas.py       # tela de desenho + navegação (pan/zoom)
│       └── icons.py        # biblioteca visual (ícones dos componentes)
└── tests/
    └── test_simulator.py   # testes da lógica de simulação
```

O **modelo** é independente da interface, então a lógica de simulação é
testável sem abrir janela:

```bash
poetry run pytest
# ou
poetry run python tests/test_simulator.py
```

## Como a simulação funciona

Cada terminal é um nó de um grafo. Fios e contatos **fechados** são condutores
ideais e unem nós na mesma "rede" (equipotencial). A fonte define os
potenciais disponíveis: cada **fase** (L ou R/S/T) é um potencial independente,
o **neutro** é outro, e o **terra (PE)** é um potencial que nunca alimenta
cargas. Uma carga de 2 terminais (bobina, lâmpada) fica **energizada** entre
uma fase e o neutro, ou entre duas fases diferentes; o **motor trifásico**
energiza quando seus terminais U1/V1/W1 estão em três fases distintas. O
estado das bobinas é iterado até estabilizar, com **memória** entre passos —
é isso que permite simular o selo.

## Limitações atuais (por design, para o MVP)

- Simulação **lógica**, não elétrica: sem valores de tensão/corrente, sem
  ligação em série de cargas com divisão de tensão.
- Um contator por vez com contatos — os contatos novos sempre pertencem à
  **última bobina** criada (padrão `K1`).
- Sem portas lógicas, temporizadores, relés térmicos, fusíveis, réguas de
  bornes, numeração automática de condutores, etc.

## Roadmap sugerido

1. **MVP atual** — desenho + ligação + simulação de comandos básicos +
   navegação (pan/zoom) + biblioteca visual.
2. **Símbolos IEC/NBR** mais fiéis e biblioteca de componentes maior
   (temporizadores, relés térmicos, fusíveis, contatos auxiliares).
3. **Edição de propriedades** (renomear contatores, associar contatos a
   bobinas específicas, múltiplos contatores).
4. **Undo/redo**, copiar/colar, seleção em área (marquee).
5. **Simulação com tempo** (temporizadores, intertravamentos, sinalização
   sequencial) e exportação de diagrama (PNG/SVG/PDF).
6. **Importar/exportar** em formatos abertos (compatibilidade futura).
