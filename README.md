# C Subset Compiler (Python)

A mini compiler for a C-like language subset, implemented in Python.
It performs lexical analysis, LL(1) and SLR(1) parsing, semantic checks, three-address code (TAC) generation, TAC optimization, and pseudo-assembly target code generation.

## Academic Context

- Subject: CS F363 Compiler Construction Lab
- College: BITS Pilani, Dubai

This compiler implementation is intentionally tailored to the given project guidelines and assignment constraints. It is not a fully general-purpose production compiler.

## Rubric and Scope Alignment

The implementation is designed around the expected rubric items in the assignment workflow, including:

- lexical analysis with error reporting
- LL(1) parsing with FIRST/FOLLOW and parse tracing
- SLR(1) parsing with trace generation
- semantic validation and symbol table handling
- TAC generation
- optimization passes (constant folding, propagation, dead code elimination)
- final target pseudo-assembly generation

The default test flow and expected outputs are aligned with the provided assignment input and reporting format.

## Features

- Regex-based lexer with line and column aware error messages.
- LL(1) parser:
  - FIRST/FOLLOW computation.
  - Predictive parsing table construction.
  - Parse trace generation.
  - Semantic checks (declaration and basic type checks).
- SLR(1) parser:
  - LR(0)-style item/state table construction.
  - Shift/reduce parse trace generation.
  - Semantic checks.
  - TAC generation as quadruples.
- Symbol table with nested scope support and memory offset tracking.
- Optimization pipeline:
  - Constant folding.
  - Constant propagation.
  - Dead code elimination.
- Target pseudo-assembly code generation with simple register allocation.

## Language Supported

The project supports a C-like subset with:

- Types: `int`, `float`
- Statements:
  - Variable declaration with optional initialization
  - Assignment
  - `if/else`
  - `while`
  - `print(...)`
  - Block scopes `{ ... }`
- Arithmetic operators: `+`, `-`, `*`, `/`, `%`
- Relational operators: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Boolean operators: `&&`, `||`, `!`

### Grammar (from parser implementation)

```text
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

## Project Structure

```text
.
|-- main.py
|-- viz.py
|-- code.txt
|-- full_demo_output.txt
|-- app/
|   |-- session.py
|   `-- tui.py
|-- compiler_core/
|   |-- frames.py
|   |-- pipeline.py
|   |-- helper/
|   |   |-- code_gen.py
|   |   |-- optimizer.py
|   |   `-- tac_manager.py
|   `-- src/
|       |-- derivation.py
|       |-- lexer.py
|       |-- lr_parser.py
|       |-- parser.py
|       `-- symbol_table.py
|-- input/
|   `-- input.txt
|-- output/
|   |-- tac_output.txt
|   |-- optimized_tac_output.txt
|   `-- target_output.txt
`-- traces/
    |-- ll1_trace.txt
    `-- slr_trace.txt
```

## Requirements

- Python 3.10+
- Python package dependencies listed in `requirements.txt`

## Setup

### 1) Create and activate a virtual environment (recommended)

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

## Running the Compiler

Default input file (`./input/input.txt`):

```bash
python main.py
```

Custom input file:

```bash
python main.py path/to/source_file.txt
```

## Running the Visualizer

The compiler includes an interactive Textual TUI dashboard for step-by-step state visualization of all compilation stages.

```bash
python viz.py [path/to/source_file.txt]
```

### Key Bindings
- `Right` or `N`: Advance to the next step frame.
- `Left` or `P`: Go back to the previous step frame.
- `Home`: Jump to the first step of the current phase.
- `End`: Jump to the last step of the current phase.
- `Q`: Quit the visualizer application.
- `Tab` / `Shift+Tab`: Shift focus between panel widgets.

## Compilation Pipeline

`main.py` runs stages in this order:

1. Read source program text.
2. Lexical analysis (`compiler_core/src/lexer.py`).
3. LL(1) parsing and semantic checks (`compiler_core/src/parser.py`).
4. SLR(1) parsing and semantic checks (`compiler_core/src/lr_parser.py`).
5. Symbol table reports for both parser passes.
6. TAC generation and display.
7. Optimization passes (`compiler_core/helper/optimizer.py`).
8. Pseudo-assembly generation (`compiler_core/helper/code_gen.py`).
9. Write outputs to files in `output/`.

If lexical or semantic errors are found, later phases are skipped appropriately.

## Generated Outputs

### In `output/`

- `tac_output.txt`: Raw TAC quadruples.
- `optimized_tac_output.txt`: TAC after optimization passes.
- `target_output.txt`: Generated pseudo-assembly instructions.

### In `traces/`

- `ll1_trace.txt`: Full LL(1) parse trace.
- `slr_trace.txt`: Full SLR(1) parse trace.

## Semantic Checks Implemented

Across LL(1) and SLR(1) flows, the compiler reports checks such as:

- Multiple declaration in the same scope.
- Use of undeclared identifiers.
- Type mismatch assigning float values to int variables.
- Invalid float comparisons using `==` or `!=` in boolean relational checks.

## Example Input

The default sample program is in `input/input.txt` and includes:

- variable declarations
- while loops
- nested if/else blocks
- arithmetic and boolean expressions
- print statements

You can also test semantic failures using `code.txt`.

### Important Project Note

The compiler behavior, output formatting, and demonstration traces are optimized for the supplied assignment inputs and evaluation expectations. If you use significantly different grammar constructs or language features, behavior may fall outside the intended project scope unless you extend the grammar and semantic rules.

## Notes on Target Code

The generated target code is pseudo-assembly (educational IR-to-target step), not tied to a specific CPU architecture.
It includes instructions such as:

- data movement: `LOAD`, `STORE`, `MOV`
- arithmetic: `ADD`, `SUB`, `MUL`, `DIV`, `MOD`
- comparisons: `SLT`, `SGT`, `SLE`, `SGE`, `SEQ`, `SNE`
- control flow: labels, `JMP`, conditional jump `JZ`
- logical ops: `AND`, `OR`, `NOT`
- output: `PRINT`

## Troubleshooting

- `ModuleNotFoundError: No module named 'textual'` or `rich`
  - Install dependencies again: `pip install -r requirements.txt`
- `python` command not found
  - Use `python3` instead on macOS/Linux.
- PowerShell script execution policy error while activating venv
  - Run PowerShell as admin and set execution policy if needed:
    `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
