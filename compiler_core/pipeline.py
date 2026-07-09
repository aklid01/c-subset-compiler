"""
Pipeline module for compiler visualization.
Coordinates execution of compiler stages and captures intermediate StepFrames.
"""

from compiler_core.frames import PhaseCapture, StepFrame
from compiler_core.helper.code_gen import generate_capture
from compiler_core.helper.optimizer import optimize_capture
from compiler_core.src.constants import TYPE_SIZES
from compiler_core.src.lexer import tokenize_capture
from compiler_core.src.lr_parser import SLRParser
from compiler_core.src.parser import LL1Parser


def run_all_captures(source: str) -> dict[str, PhaseCapture]:
    """Run compiler stages on source and return a dictionary of captured phases."""
    captures = {}

    # 1. Lexer
    lex_capture = tokenize_capture(source)
    captures["lexer"] = lex_capture
    if not lex_capture.success:
        return captures

    # Reconstruct tokens list from lexer frames
    tokens = []
    for f in lex_capture.frames:
        d = f.detail
        from compiler_core.src.tokens import Token

        tokens.append(Token(d["kind"], d["value"], d["line"], d["column"]))

    # 2. LL(1) Parser
    ll1 = LL1Parser(tokens)
    ll1_capture = ll1.parse_capture()
    captures["ll1_parser"] = ll1_capture
    if not ll1_capture.success:
        return captures

    # 3. SLR(1) Parser & TAC
    slr = SLRParser(tokens, ll1)
    tac_frames = []
    slr_capture = slr.parse_capture(tac_capture_list=tac_frames)
    captures["slr_parser"] = slr_capture

    if not slr_capture.success:
        return captures

    # 3b. TAC Capture (from tac_frames)
    tac_final_output = []
    if tac_frames:
        final_quads = tac_frames[-1].context["quads"]
        from compiler_core.helper.tac_manager import TACManager

        mock_tac = TACManager()
        mock_tac.quads = final_quads
        mock_tac.temp_count = len({q[3] for q in final_quads if q[3].startswith("t")})
        mock_tac.label_count = len({q[3] for q in final_quads if q[3].startswith("L")})
        tac_final_output = (
            [
                "THREE-ADDRESS CODE  (Quadruples)",
                "============================================================",
            ]
            + mock_tac._lines(final_quads)
            + [
                "============================================================",
                f"Total quads : {len(final_quads)}",
                f"Temporaries : {mock_tac.temp_count}",
                f"Labels      : {mock_tac.label_count}",
                "============================================================",
            ]
        )

    tac_capture = PhaseCapture(
        name="tac", frames=tac_frames, success=True, final_output=tac_final_output
    )
    captures["tac"] = tac_capture

    # 3c. Symbol Table Capture (from slr.symbol_table log)
    symbol_table_log = slr.symbol_table.log
    symbol_table_history = slr.symbol_table.history

    st_frames = []
    alloc_count = 0
    for i, entry in enumerate(symbol_table_log):
        if "Allocating" in entry:
            alloc_count += 1

        vars_so_far = [
            {
                "name": name,
                "type": sym.data_type,
                "scope": sym.scope_level,
                "offset": sym.offset,
            }
            for name, sym in symbol_table_history[:alloc_count]
        ]

        st_frames.append(
            StepFrame(
                phase="symbol_table",
                index=i,
                title=entry,
                detail={"log_entry": entry},
                context={
                    "variables": vars_so_far,
                    "next_offset": (
                        symbol_table_history[alloc_count - 1][1].offset
                        + TYPE_SIZES.get(
                            symbol_table_history[alloc_count - 1][1].data_type.lower(), 4
                        )
                        if alloc_count > 0
                        else 0
                    ),
                },
            )
        )

    captures["symbol_table"] = PhaseCapture(
        name="symbol_table",
        frames=st_frames,
        success=True,
        final_output=slr.symbol_table.format_report("SLR"),
    )

    # Check semantic errors
    all_semantic_errors = ll1.semantic_errors + slr.semantic_errors
    if all_semantic_errors:
        return captures

    # 4. TAC Optimization
    final_quads = tac_frames[-1].context["quads"] if tac_frames else []
    opt_capture = optimize_capture(final_quads)
    captures["optimizer"] = opt_capture

    # 5. Target Code Generation
    opt_quads = opt_capture.frames[-1].context["quads"] if opt_capture.frames else final_quads
    code_gen_capture = generate_capture(opt_quads)
    captures["code_gen"] = code_gen_capture

    return captures
