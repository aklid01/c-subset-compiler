"""
Semantics checking module for the C-subset compiler.
Contains shared functions for type resolution and boolean condition checks.
"""

from compiler_core.src.symbol_table import SymbolTable


def resolve_type(symbol_table: SymbolTable, tok_kind: str, tok_val: str) -> str | None:
    """Resolve the data type of a token kind/value against the symbol table."""
    if tok_kind == "FLOAT":
        return "float"
    if tok_kind == "INT":
        return "int"
    if tok_kind == "ID":
        sym = symbol_table.lookup(tok_val)
        return sym.data_type if sym else None
    return None


def check_bool_condition(
    symbol_table: SymbolTable,
    errors_list: list[str],
    lhs_tok: tuple[str, str] | tuple[str, str, int, int],
    relop_val: str,
    rhs_tok: tuple[str, str] | tuple[str, str, int, int],
    line: int,
) -> None:
    """Check boolean condition validity, ensuring floats are not compared using == or !=."""
    if relop_val not in ("==", "!="):
        return
    lhs_type = resolve_type(symbol_table, lhs_tok[0], lhs_tok[1])
    rhs_type = resolve_type(symbol_table, rhs_tok[0], rhs_tok[1])
    if lhs_type == "float" or rhs_type == "float":
        errors_list.append(
            f"[Error] Invalid Boolean Condition at line {line}: "
            f"operator '{relop_val}' cannot be used with float operands "
            f"('{lhs_tok[1]}' {relop_val} '{rhs_tok[1]}'). "
            f"Use '<', '>', '<=', '>=' for float comparisons."
        )
