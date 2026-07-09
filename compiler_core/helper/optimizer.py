"""
Optimizer module for the C-subset compiler.
Provides constant folding, constant propagation, and dead code elimination (DCE)
passes to optimize generated Three-Address Code (TAC).
"""

import copy

_ARITH_OPS = {"+", "-", "*", "/", "%"}
_RELOP_OPS = {"<", ">", "<=", ">=", "==", "!="}
_ALL_OPS = _ARITH_OPS | _RELOP_OPS
_ALWAYS_KEEP = {"LABEL", "GOTO", "IF_FALSE", "IF_TRUE", "PRINT"}


def _is_const(val):
    try:
        float(str(val))
        return True
    except (TypeError, ValueError):
        return False


def _as_num(val):
    s = str(val)
    return float(s) if "." in s else int(s)


def _fmt(val):
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    return str(val)


def _eval_arith(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            return None
        return a / b if isinstance(a, float) or isinstance(b, float) else a // b
    if op == "%":
        if b == 0:
            return None
        return a % b
    return None


def _eval_relop(op, a, b):
    if op == "<":
        return int(a < b)
    if op == ">":
        return int(a > b)
    if op == "<=":
        return int(a <= b)
    if op == ">=":
        return int(a >= b)
    if op == "==":
        return int(a == b)
    if op == "!=":
        return int(a != b)
    return None


def constant_folding(quads: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """Fold arithmetic operations on numeric constants into a single constant assignment."""
    quads = copy.deepcopy(quads)
    log = []
    for i, q in enumerate(quads):
        op, arg1, arg2, res = q
        if op in _ARITH_OPS and _is_const(arg1) and _is_const(arg2):
            val = _eval_arith(op, _as_num(arg1), _as_num(arg2))
            if val is not None:
                log.append(f"  [{i:>3}] {arg1} {op} {arg2}  →  {_fmt(val)}")
                quads[i] = ["=", _fmt(val), "-", res]
        elif op in _RELOP_OPS and _is_const(arg1) and _is_const(arg2):
            val = _eval_relop(op, _as_num(arg1), _as_num(arg2))
            if val is not None:
                log.append(f"  [{i:>3}] {arg1} {op} {arg2}  →  {val}")
                quads[i] = ["=", str(val), "-", res]
    return quads, log


def constant_propagation(quads: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """Propagate constant values into subsequent uses until re-assignment or jump labels."""
    quads = copy.deepcopy(quads)
    log = []
    const_map = {}

    jump_targets = set()
    for q in quads:
        if q[0] in ("IF_FALSE", "IF_TRUE", "GOTO"):
            jump_targets.add(str(q[3]))

    for i, q in enumerate(quads):
        op, arg1, arg2, res = q

        if op == "LABEL" and str(res) in jump_targets:
            const_map.clear()
            continue

        new_arg1, new_arg2 = str(arg1), str(arg2)
        if op not in _ALWAYS_KEEP:
            if str(arg1) in const_map:
                new_arg1 = const_map[str(arg1)]
                log.append(f"  [{i:>3}] replaced '{arg1}' with '{new_arg1}' in arg1")
                quads[i][1] = new_arg1
            if str(arg2) in const_map and str(arg2) != "-":
                new_arg2 = const_map[str(arg2)]
                log.append(f"  [{i:>3}] replaced '{arg2}' with '{new_arg2}' in arg2")
                quads[i][2] = new_arg2

        if op == "=" and _is_const(quads[i][1]) and str(res) not in ("-", "PENDING"):
            const_map[str(res)] = str(quads[i][1])
        elif str(res) not in ("-", "PENDING", "") and op not in _ALWAYS_KEEP:
            const_map.pop(str(res), None)

    return quads, log


def dead_code_elimination(quads: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """Remove unused temporary variable definitions that do not affect program output."""
    quads = copy.deepcopy(quads)
    log = []

    def _uses(q):
        op, arg1, arg2, res = q
        used = set()
        if op == "IF_FALSE" or op == "IF_TRUE":
            used.add(str(arg1))
        elif op == "PRINT":
            used.add(str(arg1))
        elif op not in _ALWAYS_KEEP:
            if str(arg1) != "-":
                used.add(str(arg1))
            if str(arg2) != "-":
                used.add(str(arg2))
        return used

    def _def(q):
        op, arg1, arg2, res = q
        if op in _ALWAYS_KEEP:
            return None
        r = str(res)
        return r if r not in ("-", "PENDING", "") else None

    changed = True
    while changed:
        changed = False
        all_used = set()
        for q in quads:
            all_used |= _uses(q)
        new_quads = []
        for i, q in enumerate(quads):
            d = _def(q)
            if d and d.startswith("t") and d not in all_used and q[0] not in _ALWAYS_KEEP:
                log.append(f"  [{i:>3}] removed dead: '{d}' = {q[0]} {q[1]} {q[2]}")
                changed = True
            else:
                new_quads.append(q)
        quads = new_quads

    return quads, log


def optimize(quads: list[list[str]]) -> tuple[list[list[str]], str]:
    """Optimize Three-Address Code by executing folding, propagation,
    and dead code elimination passes.
    """
    width = 62
    lines = []
    lines.append("\n" + "═" * width)
    lines.append(" OPTIMIZATION REPORT ".center(width, "═"))
    lines.append("═" * width)
    lines.append(f"  Original quad count : {len(quads)}")
    lines.append("─" * width)

    current_quads = copy.deepcopy(quads)
    pass_index = 1
    while True:
        next_quads, fold_log = constant_folding(current_quads)
        next_quads, prop_log = constant_propagation(next_quads)

        if next_quads == current_quads:
            break

        if pass_index == 1:
            lines.append("\n  Pass 1 – Constant Folding")
            lines.append("  " + "─" * (width - 2))
            lines += fold_log if fold_log else ["  (nothing to fold)"]

            lines.append("\n  Pass 2 – Constant Propagation")
            lines.append("  " + "─" * (width - 2))
            lines += prop_log if prop_log else ["  (nothing to propagate)"]
        elif pass_index == 2:
            lines.append("\n  Pass 1 (repeat) – Constant Folding on propagated values")
            lines.append("  " + "─" * (width - 2))
            lines += fold_log if fold_log else ["  (nothing new to fold)"]

            lines.append("\n  Pass 2 (repeat) – Constant Propagation")
            lines.append("  " + "─" * (width - 2))
            lines += prop_log if prop_log else ["  (nothing new to propagate)"]
        else:
            lines.append(f"\n  Pass {2 * pass_index - 1} – Constant Folding")
            lines.append("  " + "─" * (width - 2))
            lines += fold_log if fold_log else ["  (nothing new to fold)"]

            lines.append(f"\n  Pass {2 * pass_index} – Constant Propagation")
            lines.append("  " + "─" * (width - 2))
            lines += prop_log if prop_log else ["  (nothing new to propagate)"]

        current_quads = next_quads
        pass_index += 1

    lines.append("\n  Pass 3 – Dead Code Elimination")
    lines.append("  " + "─" * (width - 2))
    final_quads, dce_log = dead_code_elimination(current_quads)
    lines += dce_log if dce_log else ["  (no dead code found)"]

    removed = len(quads) - len(final_quads)
    lines.append("\n" + "─" * width)
    lines.append(f"  Optimized quad count : {len(final_quads)}  (removed {removed})")
    lines.append("═" * width + "\n")

    return final_quads, "\n".join(lines)
