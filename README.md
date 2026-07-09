# C-Subset Compiler (Python)

A mini compiler for a C-like language subset, implemented in Python. It performs the full classical pipeline — **lexical analysis → LL(1) & SLR(1) parsing → semantic checks → three-address code (TAC) generation → TAC optimization → pseudo-assembly target code** — and ships with an interactive **step-by-step terminal visualizer**.

> **Academic Context** — CS F363 Compiler Construction Lab, BITS Pilani, Dubai. This implementation is intentionally scoped to the assignment guidelines and is not a general-purpose production compiler.

---

## Table of Contents
- [Highlights](#highlights)
- [Quick Start](#quick-start)
- [Running the Compiler](#running-the-compiler)
- [Running the Visualizer](#running-the-visualizer)
- [Project Structure](#project-structure)
- [Compilation Pipeline](#compilation-pipeline)
- [Language Reference](#language-reference)
- [Generated Outputs](#generated-outputs)
- [Semantic Checks](#semantic-checks)
- [Target Code Notes](#target-code-notes)
- [Troubleshooting](#troubleshooting)

---

## Highlights

- **Regex-based lexer** with line- and column-aware error reporting.
- **LL(1) parser** — FIRST/FOLLOW computation, predictive parse table, full parse tracing.
- **SLR(1) parser** — LR(0) item/state construction, shift/reduce trace, TAC generation.
- **Symbol table** with nested scopes and memory-offset tracking.
- **Optimizer** — constant folding, constant propagation, and dead-code elimination.
- **Target code generator** — pseudo-assembly with liveness analysis and register allocation.
- **Interactive visualizer** — a Textual TUI to step through every phase, frame by frame.

The codebase is organized so the **pure compiler logic** (`compiler_core/`) is fully decoupled from **presentation** (console rendering + the visualizer front-end in `app/`). The compiler core has zero dependency on the visualizer, so `python main.py` runs without any TUI libraries loaded.

---

## Quick Start

Requires **Python 3.10+**.

### 1) Create and activate a virtual environment (recommended)

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

Dependencies: `textual` and `rich` (used only by the visualizer). The batch compiler itself relies solely on the Python standard library.

---

## Running the Compiler

Run the full batch pipeline and write all reports/artifacts to disk.

```bash
# Default input (./input/input.txt)
python main.py

# Custom source file
python main.py path/to/source_file.txt
```

Console output includes FIRST/FOLLOW sets, LL(1) and SLR(1) parse previews, symbol-table reports, the semantic-analysis summary, TAC, the optimization report, and the final target code. If lexical or semantic errors are found, later phases are skipped and a clear error report is printed instead.

---

## Running the Visualizer

An interactive terminal dashboard that lets you walk through each compilation phase one step at a time, inspecting live state (parse stacks, symbol table, TAC, optimizations, register allocation).

```bash
# Default input
python viz.py

# Custom source file
python viz.py path/to/source_file.txt
```

Select a phase from the left sidebar, then scrub through its steps.

### Key Bindings

| Key | Action |
|-----|--------|
| `Right` / `N` | Next step |
| `Left` / `P` | Previous step |
| `Home` | Jump to first step of the phase |
| `End` | Jump to last step of the phase |
| `O` | Show where `output/` artifacts are written |
| `Tab` / `Shift+Tab` | Move focus between panels |
| `Q` | Quit |

If the loaded source contains compilation or semantic errors, the visualizer shows the phases only up to the point of failure and displays a warning banner.

Tip: use the bundled `code.txt` to see how the visualizer surfaces semantic failures.

---

## Project Structure

```
.
|-- main.py                     # Batch CLI entry point
|-- viz.py                      # Interactive visualizer entry point
|-- code.txt                    # Sample input with intentional semantic errors
|-- full_demo_output.txt        # Reference console output
|-- requirements.txt
|-- app/                        # Visualizer front-end (Textual/rich)
|   |-- session.py              # Headless navigation state (phase + frame pointers)
|   `-- tui.py                  # Textual TUI dashboard
|-- compiler_core/              # Pure compiler logic (no visualizer deps)
|   |-- frames.py               # StepFrame / PhaseCapture dataclasses
|   |-- pipeline.py             # run_all_captures(): orchestrates capture of all phases
|   |-- helper/
|   |   |-- code_gen.py         # Target pseudo-assembly + register allocation
|   |   |-- optimizer.py        # Folding / propagation / dead-code elimination
|   |   `-- tac_manager.py      # TAC emission, temps/labels, backpatching
|   `-- src/
|       |-- lexer.py            # Tokenizer
|       |-- parser.py           # LL(1) parser + FIRST/FOLLOW
|       |-- lr_parser.py        # SLR(1) parser + TAC generation
|       |-- symbol_table.py     # Scoped symbol table
|       |-- semantics.py        # Shared semantic checks
|       |-- tokens.py           # Token type + pretty-name map
|       |-- constants.py        # Central limits, sizes, widths
|-- input/
|   `-- input.txt               # Default sample program
|-- output/                     # Generated: TAC, optimized TAC, target code
`-- traces/                     # Generated: LL(1) and SLR(1) parse traces
```

---

## Compilation Pipeline

`main.py` runs the stages in this order:

1. **Read** source program text.
2. **Lexical analysis** — `compiler_core/src/lexer.py`
3. **LL(1) parsing** + semantic checks — `compiler_core/src/parser.py`
4. **SLR(1) parsing** + semantic checks + TAC generation — `compiler_core/src/lr_parser.py`
5. **Symbol-table reports** for both parser passes.
6. **TAC display** — `compiler_core/helper/tac_manager.py`
7. **Optimization passes** — `compiler_core/helper/optimizer.py`
8. **Target code generation** — `compiler_core/helper/code_gen.py`
9. **Write outputs** to `output/` and `traces/`.

Errors short-circuit the pipeline: lexical errors stop before parsing, and semantic errors stop before TAC generation.

---

## Language Reference

### Types
`int`, `float`

### Statements
- Variable declaration with optional initialization
- Assignment
- `if` / `else`
- `while`
- `print(...)`
- Block scopes `{ ... }`

### Operators
- **Arithmetic:** `+  -  *  /  %`
- **Relational:** `<  >  <=  >=  ==  !=`
- **Boolean:** `&&  ||  !`

### Grammar
```
Program    -> StmtList
StmtList   -> Stmt StmtList | epsilon
Stmt       -> Decl | AssignStmt | IfStmt | WhileStmt | PrintStmt | Block
Decl       -> Type ID DeclTail
DeclTail   -> ASSIGN Expr SEMI | SEMI
Type       -> INT | FLOAT
Block      -> LBRACE StmtList RBRACE
AssignStmt -> ID ASSIGN Expr SEMI
PrintStmt  -> PRINT LPAREN Expr RPAREN SEMI
IfStmt     -> IF LPAREN BoolExpr RPAREN Stmt ElsePart
ElsePart   -> ELSE Stmt | epsilon
WhileStmt  -> WHILE LPAREN BoolExpr RPAREN Stmt
Expr       -> Term Expr'
Expr'      -> PLUS Term Expr' | MINUS Term Expr' | epsilon
Term       -> Factor Term'
Term'      -> MULT Factor Term' | DIV Factor Term' | MOD Factor Term' | epsilon
Factor     -> LPAREN Expr RPAREN | ID | INT | FLOAT
BoolExpr   -> BoolTerm BoolExpr'
BoolExpr'  -> OR BoolTerm BoolExpr' | epsilon
BoolTerm   -> BoolFactor BoolTerm'
BoolTerm'  -> AND BoolFactor BoolTerm' | epsilon
BoolFactor -> NOT BoolFactor | RelExpr | LPAREN BoolExpr RPAREN
RelExpr    -> Expr RelOp Expr
RelOp      -> LT | GT | LE | GE | EQ | NE
```

### Example Input
The default program (`input/input.txt`) exercises declarations, `while` loops, nested `if`/`else`, arithmetic and boolean expressions, and `print`. Use `code.txt` to trigger semantic failures.

---

## Generated Outputs

### `output/`
| File | Contents |
|------|----------|
| `tac_output.txt` | Raw TAC quadruples |
| `optimized_tac_output.txt` | TAC after optimization passes |
| `target_output.txt` | Generated pseudo-assembly |

### `traces/`
| File | Contents |
|------|----------|
| `ll1_trace.txt` | Full LL(1) parse trace |
| `slr_trace.txt` | Full SLR(1) parse trace |

---

## Semantic Checks

Across the LL(1) and SLR(1) flows, the compiler reports:

- Multiple declaration of a variable in the same scope.
- Use of an undeclared identifier.
- Type mismatch when assigning a float value to an `int` variable.
- Invalid float comparisons using `==` or `!=` in boolean relational checks.

---

## Target Code Notes

The generated target code is **pseudo-assembly** (an educational IR-to-target step), not tied to a specific CPU architecture. Instruction families include:

- **Data movement:** `LOAD`, `STORE`, `MOV`
- **Arithmetic:** `ADD`, `SUB`, `MUL`, `DIV`, `MOD`
- **Comparisons:** `SLT`, `SGT`, `SLE`, `SGE`, `SEQ`, `SNE`
- **Control flow:** labels, `JMP`, conditional jump `JZ`
- **Logical:** `AND`, `OR`, `NOT`
- **Output:** `PRINT`

The visualizer's Target Code view shows the exact same instruction stream that is written to `output/target_output.txt`.

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'textual'` (or `rich`)** — reinstall dependencies: `pip install -r requirements.txt`. These are only needed for `viz.py`; `main.py` runs without them.
- **`python: command not found`** — use `python3` on macOS/Linux.
- **PowerShell execution-policy error when activating the venv** — run PowerShell as admin and set: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`.
- **Garbled characters (e.g. the epsilon symbol) in the Windows console** — the tools force UTF-8 output; ensure your terminal uses a UTF-8 capable font.

---

### Project Note
Behavior, output formatting, and demonstration traces are tuned to the supplied assignment inputs and evaluation expectations. Significantly different grammar constructs may fall outside the intended scope unless you extend the grammar and semantic rules.
