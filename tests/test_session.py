from app.session import VizSession


def test_session_navigation_success():
    with open("input/input.txt") as f:
        source = f.read()

    session = VizSession(source)

    # Initial state
    assert session.current_phase == "lexer"
    assert session.frame_index == 0
    assert len(session.get_phases()) > 0

    # Test get_current_frame
    frame = session.get_current_frame()
    assert frame is not None
    assert frame.phase == "lexer"

    # Test next_step boundary
    lexer_len = len(session.captures["lexer"].frames)
    for _ in range(lexer_len - 1):
        assert session.next_step()
    # At boundary
    assert not session.next_step()

    # Test prev_step boundary
    for _ in range(lexer_len - 1):
        assert session.prev_step()
    # At boundary
    assert not session.prev_step()

    # Test jump_to_end
    session.jump_to_end()
    assert session.frame_index == lexer_len - 1

    # Test jump_to_start
    session.jump_to_start()
    assert session.frame_index == 0

    # Test select_phase resets frame_index
    session.jump_to_end()
    session.select_phase("ll1_parser")
    assert session.current_phase == "ll1_parser"
    assert session.frame_index == 0
