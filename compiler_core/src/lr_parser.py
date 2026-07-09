"""
LR/SLR Parser module for the C-subset compiler.
Implements an SLR(1) parser with DFA construction (LR(0) collection)
and three-address code (TAC) generation with semantic checking.
This is the third stage in the compiler pipeline.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compiler_core.frames import PhaseCapture

from compiler_core.helper.tac_manager import TACManager
from compiler_core.src.constants import CONSOLE_TRACE_LIMIT, RELOPS, REPORT_WIDTH
from compiler_core.src.semantics import check_bool_condition
from compiler_core.src.symbol_table import SymbolTable
from compiler_core.src.tokens import PRETTY_NAMES, Token

_NO_OP = object()


class SLRParser:
    def __init__(self, tokens: list[Token], base_parser):
        """Initialize the SLR(1) parser with token stream and base parser (for sets)."""
        if not tokens or tokens[-1].kind != "EOF":
            self.tokens = tokens + [Token("EOF", "$", -1, -1)]
        else:
            self.tokens = tokens
        self.symbol_table = SymbolTable()
        self.pos = 0
        self.semantic_errors = []
        self.grammar = base_parser.grammar
        self.follow = base_parser.follow
        self.start_symbol = "Program'"
        self.augmented_grammar = {self.start_symbol: [["Program"]]}
        self.augmented_grammar.update(self.grammar)
        self.rules_list = []
        for lhs, prods in self.augmented_grammar.items():
            for rhs in prods:
                self.rules_list.append((lhs, rhs))

        self.states = []
        self.action_table = {}
        self.goto_table = {}
        self.in_condition = False
        self.cond_paren_depth = 0
        self._build_tables()

    def _closure(self, items):
        closure_set = set(items)
        changed = True
        while changed:
            changed = False
            for lhs, rhs, dot in list(closure_set):
                if dot < len(rhs):
                    symbol = rhs[dot]
                    if symbol in self.augmented_grammar:
                        for prod in self.augmented_grammar[symbol]:
                            new_rhs = [] if prod == ["ε"] else prod
                            new_item = (symbol, tuple(new_rhs), 0)
                            if new_item not in closure_set:
                                closure_set.add(new_item)
                                changed = True
        return closure_set

    def _goto(self, items, symbol):
        moved = []
        for lhs, rhs, dot in items:
            if dot < len(rhs) and rhs[dot] == symbol:
                moved.append((lhs, rhs, dot + 1))
        return self._closure(moved)

    def _build_tables(self):
        initial = self._closure(
            {
                (
                    self.start_symbol,
                    tuple(self.augmented_grammar[self.start_symbol][0]),
                    0,
                )
            }
        )
        self.states = [frozenset(initial)]
        i = 0
        while i < len(self.states):
            state = self.states[i]
            symbols = set(sym for _, rhs, dot in state if dot < len(rhs) for sym in [rhs[dot]])
            for sym in symbols:
                next_state = frozenset(self._goto(state, sym))
                if next_state not in self.states:
                    self.states.append(next_state)
                idx = self.states.index(next_state)
                if sym in self.augmented_grammar:
                    self.goto_table[(i, sym)] = idx
                else:
                    self.action_table[(i, sym)] = f"s{idx}"
            for lhs, rhs, dot in state:
                if dot == len(rhs):
                    if lhs == self.start_symbol:
                        self.action_table[(i, "$")] = "acc"
                    else:
                        for term in self.follow.get(lhs, []):
                            if (i, term) in self.action_table:
                                continue
                            r_idx = -1
                            for idx, (r_lhs, r_rhs) in enumerate(self.rules_list):
                                if r_lhs == lhs and tuple(r_rhs if r_rhs != ["ε"] else []) == rhs:
                                    r_idx = idx
                                    break
                            if r_idx != -1:
                                self.action_table[(i, term)] = f"r{r_idx}"
            i += 1

    def _run_parse_loop(
        self, capture_list: list = None, tac_capture_list: list = None
    ) -> tuple[bool, list[dict], TACManager]:
        stack = [0]
        trace_log = []
        step = 0
        success = False
        semantic_stack = []
        control_stack = []

        self.in_condition = False
        self.cond_paren_depth = 0

        tac = TACManager(capture_list=tac_capture_list)

        relop_shifted = None
        relexpr_lhs_tok = None
        relexpr_line = None

        while True:
            step += 1
            state = stack[-1]
            token = self.tokens[self.pos]
            token_kind, token_val, line, col = token.kind, token.value, token.line, token.col
            lookahead = "$" if token_kind == "EOF" else token_kind
            action = self.action_table.get((state, lookahead))

            trace_log.append(
                {
                    "step": str(step),
                    "stack": str(stack),
                    "lookahead": lookahead,
                    "action": action if action else "ERROR",
                    "line": line,
                    "col": col,
                    "val": token_val,
                }
            )

            if capture_list is not None:
                from compiler_core.frames import StepFrame

                sym_table_snap = [
                    {
                        "name": sym.name,
                        "type": sym.data_type,
                        "scope": sym.scope_level,
                        "offset": sym.offset,
                    }
                    for name, sym in self.symbol_table.history
                ]
                capture_list.append(
                    StepFrame(
                        phase="slr_parser",
                        index=len(capture_list),
                        title=f"Step {step}: {action if action else 'ERROR'}",
                        detail=trace_log[-1],
                        context={
                            "stack": list(stack),
                            "semantic_stack": list(semantic_stack),
                            "control_stack": list(control_stack),
                            "symbol_table": sym_table_snap,
                            "semantic_errors": list(self.semantic_errors),
                            "tac": [list(q) for q in tac.quads],
                        },
                    )
                )

            if action and action.startswith("s"):
                stack.append(int(action[1:]))
                semantic_stack.append(token_val)

                self._handle_control_flow_shift(lookahead, semantic_stack, control_stack, tac)

                if lookahead == "LBRACE":
                    self.symbol_table.enter_scope()

                if lookahead in RELOPS:
                    if self.pos >= 1:
                        prev = self.tokens[self.pos - 1]
                        relexpr_lhs_tok = (prev.kind, prev.value)
                    else:
                        relexpr_lhs_tok = None
                    relop_shifted = (lookahead, token_val)
                    relexpr_line = line

                elif relop_shifted is not None and lookahead in ("ID", "INT", "FLOAT"):
                    rhs_tok = (lookahead, token_val)
                    if relexpr_lhs_tok is not None:
                        check_bool_condition(
                            self.symbol_table,
                            self.semantic_errors,
                            relexpr_lhs_tok,
                            relop_shifted[1],
                            rhs_tok,
                            relexpr_line,
                        )
                    relop_shifted = None
                    relexpr_lhs_tok = None

                self.pos += 1

            elif action and action.startswith("r"):
                rule_idx = int(action[1:])
                rule_lhs, rule_rhs = self.rules_list[rule_idx]
                pop_count = 0 if rule_rhs == ["ε"] else len(rule_rhs)

                rhs_vals = []
                for _ in range(pop_count):
                    rhs_vals.insert(0, semantic_stack.pop())

                dispatch = {
                    "Decl": lambda: self._reduce_decl(rhs_vals, line, tac),
                    "DeclTail": lambda: self._reduce_decl_tail(pop_count, rhs_vals),
                    "Factor": lambda: self._reduce_factor(rule_rhs, rhs_vals, line),
                    "Type": lambda: self._reduce_type_or_relop(rhs_vals),
                    "RelOp": lambda: self._reduce_type_or_relop(rhs_vals),
                    "BoolFactor": lambda: self._reduce_bool_factor(rhs_vals, tac),
                    "RelExpr": lambda: self._reduce_rel_expr(rhs_vals, tac),
                    "Expr'": lambda: self._reduce_expr_prime_or_term_prime(
                        pop_count, rhs_vals, tac
                    ),
                    "Term'": lambda: self._reduce_expr_prime_or_term_prime(
                        pop_count, rhs_vals, tac
                    ),
                    "Expr": lambda: self._reduce_expr_or_term(rhs_vals, tac),
                    "Term": lambda: self._reduce_expr_or_term(rhs_vals, tac),
                    "BoolExpr'": lambda: self._reduce_bool_expr_prime_or_bool_term_prime(
                        pop_count, rhs_vals, tac
                    ),
                    "BoolTerm'": lambda: self._reduce_bool_expr_prime_or_bool_term_prime(
                        pop_count, rhs_vals, tac
                    ),
                    "BoolExpr": lambda: self._reduce_bool_expr_or_bool_term(rhs_vals, tac),
                    "BoolTerm": lambda: self._reduce_bool_expr_or_bool_term(rhs_vals, tac),
                    "PrintStmt": lambda: self._reduce_print_stmt(rhs_vals, tac),
                    "AssignStmt": lambda: self._reduce_assign_stmt(rhs_vals, line, tac),
                    "WhileStmt": lambda: self._reduce_while_stmt(control_stack, tac),
                    "IfStmt": lambda: self._reduce_if_stmt(control_stack, tac),
                }

                if rule_lhs in dispatch:
                    res = dispatch[rule_lhs]()
                else:
                    res = None

                if res is _NO_OP:
                    semantic_stack.append(_NO_OP)
                elif res is not None:
                    semantic_stack.append(res)
                elif rule_rhs == ["ε"]:
                    semantic_stack.append(_NO_OP)
                else:
                    semantic_stack.append("VOID")

                if rule_lhs == "Block":
                    self.symbol_table.exit_scope()

                for _ in range(pop_count):
                    stack.pop()
                stack.append(self.goto_table[(stack[-1], rule_lhs)])

            elif action == "acc":
                success = True
                break

            else:
                expected_tokens = [t for (s, t) in self.action_table if s == state]
                friendly = [PRETTY_NAMES.get(t, t) for t in expected_tokens]
                error_msg = f"Error: Expected {friendly}, but found '{token_val}'"
                trace_log.append(
                    {
                        "step": str(step),
                        "stack": str(stack),
                        "lookahead": lookahead,
                        "action": error_msg,
                        "line": line,
                        "col": col,
                        "val": token_val,
                    }
                )
                break

        return success, trace_log, tac

    def _render_console(self, trace_log: list[dict]) -> None:
        if not trace_log:
            return
        max_step_w = max(len(d["step"]) for d in trace_log)
        max_look_w = max(len(d["lookahead"]) for d in trace_log)
        console_stack_w = 40

        console_format = (
            f"{{step:<{max_step_w}}} | {{stack:<{console_stack_w}}} "
            f"| {{lookahead:<{max_look_w}}} | {{action}}"
        )
        header = console_format.format(
            step="STEP",
            stack="STACK (States)",
            lookahead="LOOKAHEAD",
            action="ACTION",
        )
        print("\n--- SLR(1) PARSE PREVIEW ---")
        print(header + "\n" + "-" * len(header))

        for entry in trace_log[:CONSOLE_TRACE_LIMIT]:
            c_stack = entry["stack"]
            if len(c_stack) > console_stack_w:
                c_stack = "..." + c_stack[-(console_stack_w - 3) :]
            print(
                console_format.format(
                    step=entry["step"],
                    stack=c_stack,
                    lookahead=entry["lookahead"],
                    action=entry["action"],
                )
            )
        if len(trace_log) > CONSOLE_TRACE_LIMIT:
            print(f"... (Remaining {len(trace_log)-CONSOLE_TRACE_LIMIT} steps processed) ...")

    def _write_trace(self, trace_log: list[dict], output_file: str) -> None:
        if not trace_log:
            return
        os.makedirs("./traces", exist_ok=True)
        with open(f"./traces/{output_file}", "w", encoding="utf-8") as f:
            f.write("SLR(1) SUCCESSFUL PARSE TRACE\n" + "=" * 50 + "\n")
            for entry in trace_log:
                f.write(
                    f"Step {entry['step']} | Stack: {entry['stack']} "
                    f"| Lookahead: {entry['lookahead']} | Action: {entry['action']}\n"
                )
        print(f"\n[Success] SLR Parsing completed successfully in {len(trace_log)} steps.")
        print(f"[Success] Full SLR trace saved to traces/{output_file}")

    def parse(self, output_file: str = "slr_trace.txt") -> tuple[bool, TACManager]:
        """Parse the token stream using the SLR(1) parsing table and generate TAC."""
        success, trace_log, tac = self._run_parse_loop()
        self._render_console(trace_log)
        if success:
            self._write_trace(trace_log, output_file)
        else:
            failed = trace_log[-1]
            print(f"\n[Fail] SLR Syntax error at line {failed['line']}, col {failed['col']}.")
            print(f"[Fail] Found '{failed['val']}' with no valid transition in Action Table.")
            print(f"[Fail] {failed['action']}")
            print("[Fail] Parsing failed. No trace file was generated.")
        return success, tac

    def parse_capture(self, tac_capture_list: list = None) -> "PhaseCapture":
        """Parse token stream and return PhaseCapture containing StepFrames for SLR(1) parsing."""
        from compiler_core.frames import PhaseCapture

        frames = []
        success, _, tac = self._run_parse_loop(
            capture_list=frames, tac_capture_list=tac_capture_list
        )
        final_output = []
        if self.semantic_errors:
            final_output.append(f"  Total errors found: {len(self.semantic_errors)}")
            for err in self.semantic_errors:
                final_output.append(f"    {err}")
        return PhaseCapture(
            name="slr_parser",
            frames=frames,
            success=success,
            final_output=final_output,
        )

    def print_semantic_errors(self):

        if not self.semantic_errors:
            print("\n[Info] SLR(1): No semantic errors detected.\n")
            return
        width = REPORT_WIDTH
        print("\n" + "═" * width)
        print(" SLR(1) SEMANTIC ERRORS ".center(width, "═"))
        print("═" * width)
        for err in self.semantic_errors:
            print(f"  {err}")
        print("═" * width + "\n")

    def _handle_control_flow_shift(
        self, lookahead: str, semantic_stack: list, control_stack: list, tac: TACManager
    ) -> None:
        """Handle control flow operations for WHILE, IF, and ELSE during shift actions."""
        if lookahead == "WHILE":
            start_label = tac.new_label()
            tac.emit("LABEL", "-", "-", start_label)
            control_stack.append(start_label)
            self.in_condition = True
            self.cond_paren_depth = 0
        elif lookahead == "IF":
            self.in_condition = True
            self.cond_paren_depth = 0
        elif lookahead == "LPAREN" and self.in_condition:
            self.cond_paren_depth += 1
        elif lookahead == "RPAREN" and self.in_condition:
            self.cond_paren_depth -= 1
            if self.cond_paren_depth == 0:
                cond_val = semantic_stack[-2]
                jump_idx = tac.emit("IF_FALSE", cond_val, "-", "PENDING")
                control_stack.append(jump_idx)
                self.in_condition = False
        elif lookahead == "ELSE":
            goto_idx = tac.emit("GOTO", "-", "-", "PENDING")
            else_label = tac.new_label()
            tac.emit("LABEL", "-", "-", else_label)
            if control_stack and isinstance(control_stack[-1], int):
                if_false_idx = control_stack.pop()
                tac.backpatch(if_false_idx, else_label)
            control_stack.append(goto_idx)

    def _reduce_decl(self, rhs_vals: list, line: int, tac: TACManager) -> None:
        var_type = rhs_vals[0]
        var_name = rhs_vals[1]
        init_val = rhs_vals[2]
        ok = self.symbol_table.insert(var_name, var_type)
        if not ok:
            self.semantic_errors.append(
                f"[Error] Multiple Declaration: Variable '{var_name}' "
                f"at line {line} is already declared in this scope."
            )
        if init_val is not _NO_OP and init_val is not None:
            sym = self.symbol_table.lookup(var_name)
            if sym and sym.data_type == "int":
                try:
                    if "." in str(init_val):
                        self.semantic_errors.append(
                            f"[Error] Type Mismatch at line {line}: "
                            f"cannot initialise int variable '{var_name}' "
                            f"with float value '{init_val}'."
                        )
                except TypeError:
                    pass
            tac.emit("=", init_val, "-", var_name)

    def _reduce_decl_tail(self, pop_count: int, rhs_vals: list) -> any:
        if pop_count == 1:
            return _NO_OP
        return rhs_vals[1]

    def _reduce_factor(self, rule_rhs: list[str], rhs_vals: list, line: int) -> any:
        if len(rhs_vals) == 3:
            return rhs_vals[1]
        res = rhs_vals[0]
        if rule_rhs == ["ID"]:
            sym = self.symbol_table.lookup(res)
            if not sym:
                self.semantic_errors.append(
                    f"[Error] Undeclared Variable: '{res}' used at "
                    f"line {line} without prior declaration."
                )
        return res

    def _reduce_type_or_relop(self, rhs_vals: list) -> any:
        return rhs_vals[0]

    def _reduce_bool_factor(self, rhs_vals: list, tac: TACManager) -> any:
        if len(rhs_vals) == 3:
            return rhs_vals[1]
        if len(rhs_vals) == 2 and rhs_vals[0] == "!":
            res = tac.new_temp()
            tac.emit("NOT", rhs_vals[1], "-", res)
            return res
        return rhs_vals[0] if rhs_vals[0] is not _NO_OP else None

    def _reduce_rel_expr(self, rhs_vals: list, tac: TACManager) -> str:
        res = tac.new_temp()
        tac.emit(rhs_vals[1], rhs_vals[0], rhs_vals[2], res)
        return res

    def _reduce_expr_prime_or_term_prime(
        self, pop_count: int, rhs_vals: list, tac: TACManager
    ) -> any:
        if pop_count == 0:
            return _NO_OP
        op, val, inner_tail = rhs_vals
        if inner_tail is _NO_OP:
            return (op, val)
        inner_op, inner_right = inner_tail
        chained = tac.new_temp()
        tac.emit(inner_op, val, inner_right, chained)
        return (op, chained)

    def _reduce_expr_or_term(self, rhs_vals: list, tac: TACManager) -> any:
        left, tail = rhs_vals
        if tail is _NO_OP:
            return left
        op, right = tail
        res = tac.new_temp()
        tac.emit(op, left, right, res)
        return res

    def _reduce_bool_expr_prime_or_bool_term_prime(
        self, pop_count: int, rhs_vals: list, tac: TACManager
    ) -> any:
        if pop_count == 0:
            return _NO_OP
        op, right, inner_tail = rhs_vals
        if inner_tail is _NO_OP:
            return (op, right)
        inner_op, inner_right = inner_tail
        chained = tac.new_temp()
        tac.emit(inner_op, right, inner_right, chained)
        return (op, chained)

    def _reduce_bool_expr_or_bool_term(self, rhs_vals: list, tac: TACManager) -> any:
        left, tail = rhs_vals
        if tail is _NO_OP:
            return left
        op, right = tail
        res = tac.new_temp()
        tac.emit(op, left, right, res)
        return res

    def _reduce_print_stmt(self, rhs_vals: list, tac: TACManager) -> None:
        tac.emit("PRINT", rhs_vals[2], "-", "-")

    def _reduce_assign_stmt(self, rhs_vals: list, line: int, tac: TACManager) -> None:
        var_name = rhs_vals[0]
        expr_val = rhs_vals[2]
        tac.emit("=", expr_val, "-", var_name)
        sym = self.symbol_table.lookup(var_name)
        if not sym:
            self.semantic_errors.append(
                f"[Error] Undeclared Variable: '{var_name}' used at "
                f"line {line} without prior declaration."
            )
        else:
            try:
                if sym.data_type == "int" and "." in str(expr_val):
                    self.semantic_errors.append(
                        f"[Error] Type Mismatch at line {line}: "
                        f"cannot assign float value '{expr_val}' to "
                        f"int variable '{var_name}'."
                    )
            except TypeError:
                pass

    def _reduce_while_stmt(self, control_stack: list, tac: TACManager) -> None:
        if_false_idx = None
        start_label = None
        for i in range(len(control_stack) - 1, -1, -1):
            if isinstance(control_stack[i], int) and if_false_idx is None:
                if_false_idx = control_stack.pop(i)
            elif isinstance(control_stack[i], str) and start_label is None:
                start_label = control_stack.pop(i)
            if if_false_idx is not None and start_label is not None:
                break
        tac.emit("GOTO", "-", "-", start_label)
        exit_label = tac.new_label()
        tac.emit("LABEL", "-", "-", exit_label)
        tac.backpatch(if_false_idx, exit_label)

    def _reduce_if_stmt(self, control_stack: list, tac: TACManager) -> None:
        exit_label = tac.new_label()
        tac.emit("LABEL", "-", "-", exit_label)
        if control_stack and isinstance(control_stack[-1], int):
            tac.backpatch(control_stack.pop(), exit_label)
