"""
Tokens module for the C-subset compiler.
Defines the Token NamedTuple representation and unified pretty names.
"""

from typing import NamedTuple


class Token(NamedTuple):
    kind: str
    value: str
    line: int
    col: int


PRETTY_NAMES = {
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
