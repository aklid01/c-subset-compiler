"""
Target Code Generator module for the C-subset compiler.
Generates pseudo-assembly target code from optimized Three-Address Code (TAC),
performing liveness analysis and register allocation.
"""

import os

from compiler_core.src.constants import NUM_REGS

_ARITH_MAP = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}
_RELOP_MAP = {
    "<": "SLT",
    ">": "SGT",
    "<=": "SLE",
    ">=": "SGE",
    "==": "SEQ",
    "!=": "SNE",
}


def _is_imm(val):
    try:
        float(str(val))
        return True
    except (TypeError, ValueError):
        return False


def _compute_liveness(quads):
    n = len(quads)
    live_after = [set() for _ in range(n)]

    _ALWAYS_KEEP = {"LABEL", "GOTO", "IF_FALSE", "IF_TRUE", "PRINT"}

    def uses(q):
        op, a1, a2, res = q
        u = set()
        if op in ("IF_FALSE", "IF_TRUE"):
            u.add(str(a1))
        elif op == "PRINT":
            u.add(str(a1))
        elif op not in _ALWAYS_KEEP:
            if str(a1) != "-":
                u.add(str(a1))
            if str(a2) != "-":
                u.add(str(a2))
        return u

    def defs(q):
        op, a1, a2, res = q
        if op in _ALWAYS_KEEP:
            return None
        r = str(res)
        return r if r not in ("-", "PENDING", "") else None

    live = set()
    for i in range(n - 1, -1, -1):
        live_after[i] = set(live)
        live = (live - ({defs(quads[i])} - {None})) | uses(quads[i])

    return live_after


class RegisterAllocator:
    def __init__(self):
        self._regs = [f"R{i}" for i in range(NUM_REGS)]
        self._reg_to_name = {r: None for r in self._regs}
        self._name_locs: dict[str, set] = {}
        self._lru = list(self._regs)

    def _touch(self, reg):
        self._lru.remove(reg)
        self._lru.append(reg)

    def _in_reg(self, name):
        for r, n in self._reg_to_name.items():
            if n == name:
                return r
        return None

    def _evict(self, reg, instrs, live_names):
        name = self._reg_to_name[reg]
        if name is None:
            return
        locs = self._name_locs.get(name, set())
        if name in live_names and "mem" not in locs:
            instrs.append(f"    STORE  {reg}, {name}")
            self._name_locs.setdefault(name, set()).add("mem")

        self._name_locs.get(name, set()).discard(reg)
        self._reg_to_name[reg] = None

    def _alloc(self, instrs, live_names):
        for reg in self._lru:
            if self._reg_to_name[reg] is None:
                return reg

        victim = self._lru[0]
        self._evict(victim, instrs, live_names)
        return victim

    def load(self, name, instrs, live_names):
        existing = self._in_reg(name)
        if existing:
            self._touch(existing)
            return existing
        reg = self._alloc(instrs, live_names)
        instrs.append(f"    LOAD   {reg}, {name}")
        self._reg_to_name[reg] = name
        self._name_locs[name] = {reg, "mem"}
        self._touch(reg)
        return reg

    def alloc_result(self, name, instrs, live_names):
        existing = self._in_reg(name)
        if existing:
            self._name_locs[name] = {existing}
            self._touch(existing)
            return existing
        reg = self._alloc(instrs, live_names)
        self._reg_to_name[reg] = name
        self._name_locs[name] = {reg}
        self._touch(reg)
        return reg

    def mark_stored(self, name):
        self._name_locs.setdefault(name, set()).add("mem")


def generate(quads: list[list[str]]) -> list[str]:
    """Generate pseudo-assembly instructions from TAC quadruples."""
    live_after = _compute_liveness(quads)
    ra = RegisterAllocator()
    instrs = []

    for idx, q in enumerate(quads):
        op, arg1, arg2, res = [str(x) for x in q]
        live = live_after[idx]

        def get_operand(val):
            if _is_imm(val):
                reg = ra.alloc_result(f"__imm_{idx}_{val}", instrs, live)
                instrs.append(f"    LOAD   {reg}, {val}")
                return reg
            else:
                return ra.load(val, instrs, live)

        if op == "LABEL":
            instrs.append(f"{res}:")
        elif op == "GOTO":
            instrs.append(f"    JMP    {res}")
        elif op == "IF_FALSE":
            r = ra.load(arg1, instrs, live)
            instrs.append(f"    JZ     {r}, {res}")
        elif op == "=":
            if _is_imm(arg1):
                rd = ra.alloc_result(res, instrs, live)
                instrs.append(f"    LOAD   {rd}, {arg1}")
            else:
                rs = ra.load(arg1, instrs, live)
                rd = ra.alloc_result(res, instrs, live)
                if rd != rs:
                    instrs.append(f"    MOV    {rd}, {rs}")
            if not res.startswith("t"):
                instrs.append(f"    STORE  {rd}, {res}")
                ra.mark_stored(res)

        elif op in _ARITH_MAP:
            ra_r = get_operand(arg1)
            rb_r = get_operand(arg2)
            rd = ra.alloc_result(res, instrs, live)
            instrs.append(f"    {_ARITH_MAP[op]:<6} {rd}, {ra_r}, {rb_r}")

        elif op in _RELOP_MAP:
            ra_r = get_operand(arg1)
            rb_r = get_operand(arg2)
            rd = ra.alloc_result(res, instrs, live)
            instrs.append(f"    {_RELOP_MAP[op]:<6} {rd}, {ra_r}, {rb_r}")

        elif op == "&&":
            ra_r = ra.load(arg1, instrs, live)
            rb_r = ra.load(arg2, instrs, live)
            rd = ra.alloc_result(res, instrs, live)
            instrs.append(f"    AND    {rd}, {ra_r}, {rb_r}")

        elif op == "||":
            ra_r = ra.load(arg1, instrs, live)
            rb_r = ra.load(arg2, instrs, live)
            rd = ra.alloc_result(res, instrs, live)
            instrs.append(f"    OR     {rd}, {ra_r}, {rb_r}")

        elif op == "NOT":
            ra_r = ra.load(arg1, instrs, live)
            rd = ra.alloc_result(res, instrs, live)
            instrs.append(f"    NOT    {rd}, {ra_r}")

        elif op == "PRINT":
            rs = ra.load(arg1, instrs, live)
            instrs.append(f"    PRINT  {rs}")

    return instrs


def display(instrs: list[str]) -> None:
    """Display the generated target pseudo-assembly on the console."""
    width = 62
    print("\n" + "═" * width)
    print(" TARGET CODE  (Pseudo-Assembly) ".center(width, "═"))
    print("═" * width)
    for instr in instrs:
        print(instr)
    print("═" * width)
    print(f"  Total instructions : {len(instrs)}")
    print("═" * width + "\n")


def save(instrs: list[str], path: str = "./output/target_output.txt") -> None:
    """Save the generated target pseudo-assembly to a text file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("TARGET CODE  (Pseudo-Assembly)\n")
        f.write("=" * 62 + "\n")
        for instr in instrs:
            f.write(instr + "\n")
        f.write("=" * 62 + "\n")
        f.write(f"Total instructions : {len(instrs)}\n")
    print(f"[Success] Target code written to {path}")
