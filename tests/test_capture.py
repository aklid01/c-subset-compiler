from compiler_core.pipeline import run_all_captures


def test_run_all_captures_success():
    with open("input/input.txt") as f:
        source = f.read()
    captures = run_all_captures(source)

    # Assert all phases are present
    assert "lexer" in captures
    assert "ll1_parser" in captures
    assert "slr_parser" in captures
    assert "tac" in captures
    assert "symbol_table" in captures
    assert "optimizer" in captures
    assert "code_gen" in captures

    # Check lexer success
    assert captures["lexer"].success
    assert len(captures["lexer"].frames) > 0

    # Check parser success
    assert captures["ll1_parser"].success
    assert captures["slr_parser"].success

    # Check that final optimized TAC output matches our expectations
    assert len(captures["optimizer"].final_output) > 0


def test_run_all_captures_semantic_error():
    with open("code.txt") as f:
        source = f.read()
    captures = run_all_captures(source)

    # Assert successful parsing but semantic error halts optimization/codegen
    assert "lexer" in captures
    assert "ll1_parser" in captures
    assert "slr_parser" in captures
    assert "tac" in captures
    assert "symbol_table" in captures

    # Optimizer and code_gen must not be run on semantic errors
    assert "optimizer" not in captures
    assert "code_gen" not in captures
