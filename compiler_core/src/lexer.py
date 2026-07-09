"""
Lexer module for the C-subset compiler.
Performs lexical analysis by converting C-subset source code
into a stream of tokens while capturing syntax-level lexical errors.
This is the first stage in the compiler pipeline.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compiler_core.frames import PhaseCapture

from compiler_core.src.tokens import Token

token_specification = [
    ("FLOAT", r"\d+\.\d+"),
    ("INT", r"\d+"),
    ("ID", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("AND", r"&&"),
    ("OR", r"\|\|"),
    ("EQ", r"=="),
    ("NE", r"!="),
    ("LE", r"<="),
    ("GE", r">="),
    ("LT", r"<"),
    ("GT", r">"),
    ("ASSIGN", r"="),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("MULT", r"\*"),
    ("DIV", r"/"),
    ("MOD", r"%"),
    ("NOT", r"!"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("SEMI", r";"),
    ("SKIP", r"[ \t]+"),
    ("NEWLINE", r"\n"),
    ("MISMATCH", r"."),
]

keywords = {"int", "float", "if", "else", "while", "print"}

regex_pattern = re.compile("|".join("(?P<%s>%s)" % pair for pair in token_specification))


def tokenize(code: str) -> tuple[list[Token], list[str]]:
    """Tokenize the C-subset source code and return a tuple of (tokens, errors)."""
    tokens = []
    errors = []
    line_num = 1
    line_start = 0

    code_lines = code.split("\n")

    for m in regex_pattern.finditer(code):
        kind = m.lastgroup
        value = m.group()
        column = m.start() - line_start + 1

        if kind == "NEWLINE":
            line_num += 1
            line_start = m.end()
            continue

        if kind == "SKIP":
            continue

        if kind == "ID" and value in keywords:
            kind = value.upper()

        if kind == "MISMATCH":
            line_text = code_lines[line_num - 1] if line_num <= len(code_lines) else ""
            pointer = " " * (column - 1) + "^"
            error_msg = (
                f"\nLexical Error at line {line_num}, column {column}:\n"
                f"{line_text}\n"
                f"{pointer}\n"
                f"Unexpected character '{value}'\n"
            )
            errors.append(error_msg)
            continue

        tokens.append(Token(kind, value, line_num, column))

    tokens.append(Token("EOF", "$", line_num, len(code_lines[-1]) + 1 if code_lines else 1))

    return tokens, errors


def tokenize_capture(code: str) -> "PhaseCapture":
    """Tokenize the C-subset source code and return a PhaseCapture containing all StepFrames."""
    from compiler_core.frames import PhaseCapture, StepFrame

    tokens = []
    errors = []
    frames = []
    line_num = 1
    line_start = 0

    code_lines = code.split("\n")

    for m in regex_pattern.finditer(code):
        kind = m.lastgroup
        value = m.group()
        column = m.start() - line_start + 1

        if kind == "NEWLINE":
            line_num += 1
            line_start = m.end()
            continue

        if kind == "SKIP":
            continue

        if kind == "ID" and value in keywords:
            kind = value.upper()

        if kind == "MISMATCH":
            line_text = code_lines[line_num - 1] if line_num <= len(code_lines) else ""
            pointer = " " * (column - 1) + "^"
            error_msg = (
                f"\nLexical Error at line {line_num}, column {column}:\n"
                f"{line_text}\n"
                f"{pointer}\n"
                f"Unexpected character '{value}'\n"
            )
            errors.append(error_msg)
            frames.append(
                StepFrame(
                    phase="lexer",
                    index=len(frames),
                    title="Lexical Error",
                    detail={
                        "error": error_msg.strip(),
                        "line": line_num,
                        "column": column,
                        "value": value,
                    },
                    context={"tokens": [t._asdict() for t in tokens]},
                )
            )
            continue

        tok = Token(kind, value, line_num, column)
        tokens.append(tok)
        frames.append(
            StepFrame(
                phase="lexer",
                index=len(frames),
                title=f"Token: {kind}",
                detail={
                    "kind": kind,
                    "value": value,
                    "line": line_num,
                    "column": column,
                },
                context={"tokens": [t._asdict() for t in tokens]},
            )
        )

    eof_tok = Token("EOF", "$", line_num, len(code_lines[-1]) + 1 if code_lines else 1)
    tokens.append(eof_tok)
    frames.append(
        StepFrame(
            phase="lexer",
            index=len(frames),
            title="Token: EOF",
            detail={
                "kind": "EOF",
                "value": "$",
                "line": line_num,
                "column": len(code_lines[-1]) + 1 if code_lines else 1,
            },
            context={"tokens": [t._asdict() for t in tokens]},
        )
    )

    final_output = []
    if errors:
        final_output.append("Lexical Errors:")
        for err in errors:
            final_output.append(err)
    else:
        final_output.append("[Success] Lexical Analysis completed successfully.")
        final_output.append(f"Total tokens matched: {len(tokens) - 1}")
        final_output.append("\nTokens matched:")
        for t in tokens[:-1]:
            final_output.append(f"  <{t.kind}, '{t.value}', line {t.line}, col {t.col}>")

    return PhaseCapture(
        name="lexer",
        frames=frames,
        success=len(errors) == 0,
        final_output=final_output,
    )
