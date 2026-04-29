import pandas as pd
from src.symbol_table import SymbolTable


class LL1Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.symbol_table = SymbolTable()
        self.pos = 0
        self.semantic_errors = []
        self.grammar = {
            "Program": [["StmtList"]],
            "StmtList": [["Stmt", "StmtList"], ["ε"]],
            "Stmt": [
                ["Decl"],
                ["AssignStmt"],
                ["IfStmt"],
                ["WhileStmt"],
                ["PrintStmt"],
                ["Block"],
            ],
            "Decl": [["Type", "ID", "DeclTail"]],
            "DeclTail": [["ASSIGN", "Expr", "SEMI"], ["SEMI"]],
            "Type": [["INT"], ["FLOAT"]],
            "Block": [["LBRACE", "StmtList", "RBRACE"]],
            "AssignStmt": [["ID", "ASSIGN", "Expr", "SEMI"]],
            "PrintStmt": [["PRINT", "LPAREN", "Expr", "RPAREN", "SEMI"]],
            "IfStmt": [["IF", "LPAREN", "BoolExpr", "RPAREN", "Stmt", "ElsePart"]],
            "ElsePart": [["ELSE", "Stmt"], ["ε"]],
            "WhileStmt": [["WHILE", "LPAREN", "BoolExpr", "RPAREN", "Stmt"]],
            "Expr": [["Term", "Expr'"]],
            "Expr'": [["PLUS", "Term", "Expr'"], ["MINUS", "Term", "Expr'"], ["ε"]],
            "Term": [["Factor", "Term'"]],
            "Term'": [
                ["MULT", "Factor", "Term'"],
                ["DIV", "Factor", "Term'"],
                ["MOD", "Factor", "Term'"],
                ["ε"],
            ],
            "Factor": [["LPAREN", "Expr", "RPAREN"], ["ID"], ["INT"], ["FLOAT"]],
            "BoolExpr": [["BoolTerm", "BoolExpr'"]],
            "BoolExpr'": [["OR", "BoolTerm", "BoolExpr'"], ["ε"]],
            "BoolTerm": [["BoolFactor", "BoolTerm'"]],
            "BoolTerm'": [["AND", "BoolFactor", "BoolTerm'"], ["ε"]],
            "BoolFactor": [
                ["NOT", "BoolFactor"],
                ["RelExpr"],
                ["LPAREN", "BoolExpr", "RPAREN"],
            ],
            "RelExpr": [["Expr", "RelOp", "Expr"]],
            "RelOp": [["LT"], ["GT"], ["LE"], ["GE"], ["EQ"], ["NE"]],
        }
        self.first = {}
        self.follow = {}
        self.table = {}
        self.terminals = self._get_terminals()
        self.non_terminals = list(self.grammar.keys())

        self._compute_first()
        self._compute_follow()
        self._build_table()

    def _get_terminals(self):
        terms = set()
        for rules in self.grammar.values():
            for prod in rules:
                for symbol in prod:
                    if symbol not in self.grammar and symbol != "ε":
                        terms.add(symbol)
        terms.add("$")
        return terms

    def _compute_first(self):
        for nt in self.non_terminals:
            self.first[nt] = set()
        changed = True
        while changed:
            changed = False
            for nt, productions in self.grammar.items():
                for prod in productions:
                    before = len(self.first[nt])
                    if prod[0] == "ε":
                        self.first[nt].add("ε")
                    elif prod[0] in self.terminals:
                        self.first[nt].add(prod[0])
                    else:
                        for symbol in prod:
                            self.first[nt].update(self.first[symbol] - {"ε"})
                            if "ε" not in self.first[symbol]:
                                break
                        else:
                            self.first[nt].add("ε")
                    if len(self.first[nt]) > before:
                        changed = True

    def _compute_follow(self):
        for nt in self.non_terminals:
            self.follow[nt] = set()
        self.follow["Program"].add("$")

        changed = True
        while changed:
            changed = False
            for nt, productions in self.grammar.items():
                for prod in productions:
                    trailer = self.follow[nt].copy()
                    for symbol in reversed(prod):
                        if symbol in self.non_terminals:
                            before = len(self.follow[symbol])
                            self.follow[symbol].update(trailer)
                            if len(self.follow[symbol]) > before:
                                changed = True
                            if "ε" in self.first[symbol]:
                                trailer.update(self.first[symbol] - {"ε"})
                            else:
                                trailer = self.first[symbol].copy()
                        else:
                            trailer = {symbol}

        self.follow["StmtList"].add("ELSE")
        self.follow["Block"].add("ELSE")
        self.follow["Stmt"].add("ELSE")

    def _build_table(self):
        for nt in self.non_terminals:
            for term in self.terminals:
                self.table[(nt, term)] = None

        for nt, productions in self.grammar.items():
            for prod in productions:
                first_of_prod = self._get_first_of_prod(prod)
                for terminal in first_of_prod:
                    if terminal != "ε":
                        self.table[(nt, terminal)] = prod
                if "ε" in first_of_prod:
                    for terminal in self.follow[nt]:
                        if nt == "ElsePart" and terminal == "ELSE":
                            self.table[(nt, terminal)] = ["ELSE", "Stmt"]
                        else:
                            self.table[(nt, terminal)] = prod

        stmt_starts = ["INT", "FLOAT", "ID", "IF", "WHILE", "PRINT", "LBRACE"]
        for start in stmt_starts:
            self.table[("StmtList", start)] = ["Stmt", "StmtList"]

        self.table[("StmtList", "$")] = ["ε"]
        self.table[("StmtList", "RBRACE")] = ["ε"]

    def _get_first_of_prod(self, prod):
        res = set()
        if prod == ["ε"]:
            res.add("ε")
            return res
        for symbol in prod:
            if symbol in self.terminals:
                res.add(symbol)
                break
            else:
                res.update(self.first[symbol] - {"ε"})
                if "ε" not in self.first[symbol]:
                    break
        else:
            res.add("ε")
        return res

    def _resolve_type(self, tok_kind, tok_val):

        if tok_kind == "FLOAT":
            return "float"
        if tok_kind == "INT":
            return "int"
        if tok_kind == "ID":
            sym = self.symbol_table.lookup(tok_val)
            return sym.data_type if sym else None
        return None

    def _check_bool_condition(self, lhs_tok, relop_val, rhs_tok, line):

        if relop_val not in ("==", "!="):
            return
        lhs_type = self._resolve_type(*lhs_tok)
        rhs_type = self._resolve_type(*rhs_tok)
        if lhs_type == "float" or rhs_type == "float":
            self.semantic_errors.append(
                f"[Error] Invalid Boolean Condition at line {line}: "
                f"operator '{relop_val}' cannot be used with float operands "
                f"('{lhs_tok[1]}' {relop_val} '{rhs_tok[1]}'). "
                f"Use '<', '>', '<=', '>=' for float comparisons."
            )

    def parse(self, output_file="ll1_trace.txt"):
        pretty_names = {
            "SEMI": ";",
            "LPAREN": "(",
            "RPAREN": ")",
            "LBRACE": "{",
            "RBRACE": "}",
            "ASSIGN": "=",
            "PLUS": "+",
            "MINUS": "-",
            "MULT": "*",
            "DIV": "/",
            "MOD": "%",
            "INT": "integer",
            "FLOAT": "float",
            "ID": "identifier",
            "$": "end of file",
        }

        stack = ["$", "Program"]
        trace_log = []
        step = 0
        success = False

        decl_flag = False
        decl_type = None

        assign_lhs_var = None
        expect_rhs_tok = False

        relop_val = None
        relexpr_lhs = None
        relexpr_line = None

        while stack:
            step += 1
            top = stack.pop()
            token = self.tokens[self.pos]
            raw_kind, raw_val, line, col = token
            curr_kind = "$" if raw_kind == "EOF" else raw_kind

            if top == "LBRACE" and curr_kind == "LBRACE":
                self.symbol_table.enter_scope()
            elif top == "RBRACE" and curr_kind == "RBRACE":
                self.symbol_table.exit_scope()

            stack_str = str(stack + [top])
            action_str = ""

            if top == "$":
                if curr_kind == "$":
                    action_str = "Accept ✓"
                    success = True
                else:
                    action_str = f"Error: Expected end of file, found {raw_kind}"
            elif top in self.terminals:
                if top == curr_kind:
                    action_str = f"Match {raw_kind}"
                else:
                    expected_char = pretty_names.get(top, top)
                    action_str = f"Error: Missing '{expected_char}'"
            else:
                prod = self.table.get((top, curr_kind))
                if prod:
                    action_str = f"Apply {top} -> {' '.join(prod)}"
                    if top == "Decl":
                        decl_flag = True
                else:
                    expected_list = [
                        pretty_names.get(t, t) for t in (self.first[top] - {"ε"})
                    ]
                    action_str = f"Error: Expected one of {expected_list}"

            trace_log.append(
                {
                    "step": str(step),
                    "stack": stack_str,
                    "lookahead": raw_kind,
                    "action": action_str,
                    "line": line,
                    "col": col,
                    "val": raw_val,
                }
            )

            if "Error" in action_str or success:
                break

            if top in self.terminals:
                if decl_flag and top in ("INT", "FLOAT"):
                    decl_type = raw_val

                if top == "ID" and decl_flag:
                    ok = self.symbol_table.insert(raw_val, decl_type)
                    if not ok:
                        self.semantic_errors.append(
                            f"[Error] Multiple Declaration: Variable '{raw_val}' "
                            f"at line {line}, column {col} is already declared "
                            f"in this scope."
                        )
                    decl_flag = False
                    decl_type = None

                elif top == "ID":
                    sym = self.symbol_table.lookup(raw_val)
                    if not sym:
                        self.semantic_errors.append(
                            f"[Error] Undeclared Variable: '{raw_val}' used at "
                            f"line {line}, column {col} without prior declaration."
                        )

                if top == "ID" and not decl_flag:
                    assign_lhs_var = raw_val

                if top == "ASSIGN" and not decl_flag:
                    expect_rhs_tok = True

                elif expect_rhs_tok and top in ("INT", "FLOAT", "ID", "LPAREN"):
                    if raw_kind == "FLOAT" and assign_lhs_var:
                        sym = self.symbol_table.lookup(assign_lhs_var)
                        if sym and sym.data_type == "int":
                            self.semantic_errors.append(
                                f"[Error] Type Mismatch at line {line}: cannot "
                                f"assign float literal '{raw_val}' to int "
                                f"variable '{assign_lhs_var}'."
                            )
                    expect_rhs_tok = False
                    assign_lhs_var = None

                RELOPS = {"LT", "GT", "LE", "GE", "EQ", "NE"}
                if top in RELOPS:
                    relop_val = raw_val
                    relexpr_line = line
                    if self.pos >= 1:
                        prev = self.tokens[self.pos - 1]
                        relexpr_lhs = (prev[0], prev[1])
                    else:
                        relexpr_lhs = None

                elif relop_val is not None and top in ("ID", "INT", "FLOAT"):
                    rhs_tok = (raw_kind, raw_val)
                    if relexpr_lhs is not None:
                        self._check_bool_condition(
                            relexpr_lhs, relop_val, rhs_tok, relexpr_line
                        )
                    relop_val = None
                    relexpr_lhs = None

                self.pos += 1
            else:
                prod = self.table.get((top, curr_kind))
                if prod and prod != ["ε"]:
                    for symbol in reversed(prod):
                        stack.append(symbol)

        max_step_w = max(len(d["step"]) for d in trace_log)
        max_stack_w = max(len(d["stack"]) for d in trace_log)
        max_look_w = max(len(d["lookahead"]) for d in trace_log)
        max_step_w = max(max_step_w, len("STEP"))
        max_look_w = max(max_look_w, len("LOOKAHEAD"))
        header_stack_label = "STACK (Top on Right)"
        actual_stack_w = max(max_stack_w, len(header_stack_label))
        console_stack_w = min(actual_stack_w, 60)

        console_format = (
            f"{{step:<{max_step_w}}} | {{stack:<{console_stack_w}}} "
            f"| {{lookahead:<{max_look_w}}} | {{action}}"
        )
        header_console = console_format.format(
            step="STEP",
            stack=header_stack_label[:console_stack_w],
            lookahead="LOOKAHEAD",
            action="ACTION",
        )
        sep_console = "-" * len(header_console)

        print(f"\n--- LL(1) PARSE PREVIEW ---")
        print(header_console + "\n" + sep_console)
        for entry in trace_log[:75]:
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
        if len(trace_log) > 75:
            print(f"... (Remaining {len(trace_log)-75} steps processed) ...")

        if success:
            file_format = (
                f"{{step:<{max_step_w}}} | {{stack:<{actual_stack_w}}} "
                f"| {{lookahead:<{max_look_w}}} | {{action}}"
            )
            header_file = file_format.format(
                step="STEP",
                stack=header_stack_label,
                lookahead="LOOKAHEAD",
                action="ACTION",
            )
            sep_file = "-" * len(header_file)
            with open(f"./traces/{output_file}", "w", encoding="utf-8") as f:
                f.write(
                    "LL(1) SUCCESSFUL PARSE TRACE\n"
                    + sep_file
                    + "\n"
                    + header_file
                    + "\n"
                    + sep_file
                    + "\n"
                )
                for entry in trace_log:
                    f.write(file_format.format(**entry) + "\n")
            print(
                f"\n[Success] Parsing completed successfully in {len(trace_log)} steps."
            )
            print(f"[Success] Full trace saved to traces/{output_file}\n")
        else:
            failed = trace_log[-1]
            print(
                f"\n[Fail] Syntax error at line {failed['line']} and column {failed['col']}."
            )
            print(
                f"[Fail] Found '{failed['val']}' when the parser was at "
                f"{failed['stack'].split(',')[-1].strip(' []')}."
            )
            print(f"[Fail] {failed['action']}")
            print(f"[Fail] Parsing failed. No trace file was generated.")

        return success

    def print_semantic_errors(self):

        if not self.semantic_errors:
            print("\n[Info] LL(1): No semantic errors detected.\n")
            return
        width = 62
        print("\n" + "═" * width)
        print(" LL(1) SEMANTIC ERRORS ".center(width, "═"))
        print("═" * width)
        for err in self.semantic_errors:
            print(f"  {err}")
        print("═" * width + "\n")

    def display_parsing_table(self):
        print("\n--- LL(1) PARSING TABLE ---")
        data = {}
        for nt in self.non_terminals:
            data[nt] = {}
            for t in self.terminals:
                prod = self.table.get((nt, t))
                data[nt][t] = " ".join(prod) if prod else "-"
        df = pd.DataFrame.from_dict(data, orient="index")
        df = df.loc[:, (df != "-").any(axis=0)]
        print(df.to_string())

    def display_sets(self):
        print("\n--- FIRST SETS ---")
        for k, v in self.first.items():
            print(f"{k:15}: {v}")
        print("\n--- FOLLOW SETS ---")
        for k, v in self.follow.items():
            print(f"{k:15}: {v}")
        print("\n")
