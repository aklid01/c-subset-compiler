"""
LR/SLR Parser module for the C-subset compiler.
Implements an SLR(1) parser with DFA construction (LR(0) collection)
and three-address code (TAC) generation with semantic checking.
This is the third stage in the compiler pipeline.
"""

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

    def parse(self, output_file: str = "slr_trace.txt") -> tuple[bool, TACManager]:
        """Parse the token stream using the SLR(1) parsing table and generate TAC."""
        stack = [0]
        trace_log = []
        step = 0
        success = False
        semantic_stack = []
        control_stack = []

        in_condition = False
        cond_paren_depth = 0

        tac = TACManager()

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

            if action and action.startswith("s"):
                stack.append(int(action[1:]))
                semantic_stack.append(token_val)

                if lookahead == "WHILE":
                    start_label = tac.new_label()
                    tac.emit("LABEL", "-", "-", start_label)
                    control_stack.append(start_label)
                    in_condition = True
                    cond_paren_depth = 0

                if lookahead == "IF":
                    in_condition = True
                    cond_paren_depth = 0

                if lookahead == "LPAREN" and in_condition:
                    cond_paren_depth += 1

                if lookahead == "RPAREN" and in_condition:
                    cond_paren_depth -= 1
                    if cond_paren_depth == 0:
                        cond_val = semantic_stack[-2]
                        jump_idx = tac.emit("IF_FALSE", cond_val, "-", "PENDING")
                        control_stack.append(jump_idx)
                        in_condition = False

                if lookahead == "ELSE":
                    goto_idx = tac.emit("GOTO", "-", "-", "PENDING")
                    else_label = tac.new_label()
                    tac.emit("LABEL", "-", "-", else_label)
                    if control_stack and isinstance(control_stack[-1], int):
                        if_false_idx = control_stack.pop()
                        tac.backpatch(if_false_idx, else_label)
                    control_stack.append(goto_idx)

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

                res = None

                if rule_lhs == "Decl":
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

                elif rule_lhs == "DeclTail":
                    if pop_count == 1:
                        res = _NO_OP
                    else:
                        res = rhs_vals[1]

                elif rule_lhs in ("Factor", "Type", "RelOp") and len(rhs_vals) == 1:
                    res = rhs_vals[0]
                    if rule_lhs == "Factor" and rule_rhs == ["ID"]:
                        sym = self.symbol_table.lookup(res)
                        if not sym:
                            self.semantic_errors.append(
                                f"[Error] Undeclared Variable: '{res}' used at "
                                f"line {line} without prior declaration."
                            )

                elif rule_lhs == "Factor" and len(rhs_vals) == 3:
                    res = rhs_vals[1]

                elif rule_lhs == "BoolFactor" and len(rhs_vals) == 3:
                    res = rhs_vals[1]

                elif rule_lhs == "BoolFactor" and len(rhs_vals) == 2 and rhs_vals[0] == "!":
                    res = tac.new_temp()
                    tac.emit("NOT", rhs_vals[1], "-", res)

                elif rule_lhs == "BoolFactor" and len(rhs_vals) == 1:
                    res = rhs_vals[0] if rhs_vals[0] is not _NO_OP else None

                elif rule_lhs == "RelExpr" and len(rhs_vals) == 3:
                    res = tac.new_temp()
                    tac.emit(rhs_vals[1], rhs_vals[0], rhs_vals[2], res)

                elif rule_lhs == "Expr'" and pop_count == 3:
                    op, term, inner_tail = rhs_vals
                    if inner_tail is _NO_OP:
                        res = (op, term)
                    else:
                        inner_op, inner_right = inner_tail
                        chained = tac.new_temp()
                        tac.emit(inner_op, term, inner_right, chained)
                        res = (op, chained)

                elif rule_lhs == "Expr'" and pop_count == 0:
                    res = _NO_OP

                elif rule_lhs == "Term'" and pop_count == 3:
                    op, factor, inner_tail = rhs_vals
                    if inner_tail is _NO_OP:
                        res = (op, factor)
                    else:
                        inner_op, inner_right = inner_tail
                        chained = tac.new_temp()
                        tac.emit(inner_op, factor, inner_right, chained)
                        res = (op, chained)

                elif rule_lhs == "Term'" and pop_count == 0:
                    res = _NO_OP

                elif rule_lhs == "Expr" and len(rhs_vals) == 2:
                    left, tail = rhs_vals
                    if tail is _NO_OP:
                        res = left
                    else:
                        op, right = tail
                        res = tac.new_temp()
                        tac.emit(op, left, right, res)

                elif rule_lhs == "Term" and len(rhs_vals) == 2:
                    left, tail = rhs_vals
                    if tail is _NO_OP:
                        res = left
                    else:
                        op, right = tail
                        res = tac.new_temp()
                        tac.emit(op, left, right, res)

                elif rule_lhs == "BoolExpr'" and pop_count == 3:
                    op, right, inner_tail = rhs_vals
                    if inner_tail is _NO_OP:
                        res = (op, right)
                    else:
                        inner_op, inner_right = inner_tail
                        chained = tac.new_temp()
                        tac.emit(inner_op, right, inner_right, chained)
                        res = (op, chained)

                elif rule_lhs == "BoolExpr'" and pop_count == 0:
                    res = _NO_OP

                elif rule_lhs == "BoolTerm'" and pop_count == 3:
                    op, right, inner_tail = rhs_vals
                    if inner_tail is _NO_OP:
                        res = (op, right)
                    else:
                        inner_op, inner_right = inner_tail
                        chained = tac.new_temp()
                        tac.emit(inner_op, right, inner_right, chained)
                        res = (op, chained)

                elif rule_lhs == "BoolTerm'" and pop_count == 0:
                    res = _NO_OP

                elif rule_lhs == "BoolExpr" and len(rhs_vals) == 2:
                    left, tail = rhs_vals
                    if tail is _NO_OP:
                        res = left
                    else:
                        op, right = tail
                        res = tac.new_temp()
                        tac.emit(op, left, right, res)

                elif rule_lhs == "BoolTerm" and len(rhs_vals) == 2:
                    left, tail = rhs_vals
                    if tail is _NO_OP:
                        res = left
                    else:
                        op, right = tail
                        res = tac.new_temp()
                        tac.emit(op, left, right, res)

                elif rule_lhs == "PrintStmt":
                    tac.emit("PRINT", rhs_vals[2], "-", "-")

                elif rule_lhs == "AssignStmt":
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

                elif rule_lhs == "WhileStmt":
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

                elif rule_lhs == "IfStmt":
                    exit_label = tac.new_label()
                    tac.emit("LABEL", "-", "-", exit_label)
                    if control_stack and isinstance(control_stack[-1], int):
                        tac.backpatch(control_stack.pop(), exit_label)

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

        if success:
            with open(f"./traces/{output_file}", "w", encoding="utf-8") as f:
                f.write("SLR(1) SUCCESSFUL PARSE TRACE\n" + "=" * 50 + "\n")
                for entry in trace_log:
                    f.write(
                        f"Step {entry['step']} | Stack: {entry['stack']} "
                        f"| Lookahead: {entry['lookahead']} | Action: {entry['action']}\n"
                    )
            print(f"\n[Success] SLR Parsing completed successfully in {len(trace_log)} steps.")
            print(f"[Success] Full SLR trace saved to traces/{output_file}")
        else:
            failed = trace_log[-1]
            print(f"\n[Fail] SLR Syntax error at line {failed['line']}, col {failed['col']}.")
            print(f"[Fail] Found '{failed['val']}' with no valid transition in Action Table.")
            print(f"[Fail] {failed['action']}")
            print("[Fail] Parsing failed. No trace file was generated.")

        return success, tac

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
