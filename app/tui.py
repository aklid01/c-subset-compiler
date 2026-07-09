"""
TUI Visualizer Dashboard module.
Implements the interactive visualizer application using the Textual framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static, TextArea

if TYPE_CHECKING:
    from app.session import VizSession
    from compiler_core.frames import StepFrame

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class NonFocusTextArea(TextArea):
    can_focus = False


class VisualizerApp(App):
    """The interactive TUI visualizer dashboard for C-Subset Compiler."""

    TITLE = "C-Subset Compiler Interactive Visualizer"
    SUB_TITLE = "Step-by-Step State Explorer"

    BINDINGS = [
        ("left,p", "prev_frame", "Prev Step"),
        ("right,n", "next_frame", "Next Step"),
        ("home", "first_frame", "Jump to Start"),
        ("end", "last_frame", "Jump to End"),
        ("o", "show_output_info", "Check output/ Folder"),
        ("q", "quit", "Quit App"),
    ]

    DEFAULT_CSS = """
    Screen {
        background: #121212;
    }
    #layout_body {
        height: 1fr;
    }
    #sidebar {
        width: 30;
        height: 100%;
        background: #1e1e1e;
        border-right: tall #333333;
    }
    #main_container {
        height: 100%;
    }
    #step_info {
        height: 5;
        background: #1a1a1a;
        border: tall #007acc;
        content-align: center middle;
    }
    #middle_container {
        height: 1fr;
    }
    #state_context {
        width: 1fr;
        height: 100%;
        background: #151515;
        border: tall #444444;
    }
    #source_code {
        width: 1fr;
        height: 100%;
        background: #151515;
        border: tall #444444;
        overflow-y: auto;
    }
    #assembly_code_viewer {
        height: 1fr;
        background: #121212;
        border: tall #00bcd4;
        display: none;
    }
    """

    def __init__(self, session: VizSession):
        super().__init__()
        self.session = session
        self.phase_map = {
            "lexer": "Lexer",
            "ll1_parser": "LL(1) Parser",
            "slr_parser": "SLR(1) Parser",
            "symbol_table": "Symbol Table",
            "tac": "Three-Address Code",
            "optimizer": "Optimizer",
            "code_gen": "Target Code",
        }

    def compose(self) -> ComposeResult:
        list_items = []
        for phase in self.session.get_phases():
            label = self.phase_map.get(phase, phase)
            list_items.append(ListItem(Label(label), id=f"item_{phase}"))

        yield Header()

        with Horizontal(id="layout_body"):
            yield Container(ListView(*list_items, id="phase_list"), id="sidebar")

            with Vertical(id="main_container"):
                yield Static(id="step_info")
                with Horizontal(id="middle_container"):
                    with ScrollableContainer(id="state_context"):
                        yield Static(id="state_context_content")
                        yield NonFocusTextArea(
                            id="assembly_code_viewer",
                            read_only=True,
                        )
                    yield NonFocusTextArea(
                        self.session.source,
                        language="c",
                        id="source_code",
                        read_only=True,
                    )

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#phase_list").index = 0
        self.query_one("#assembly_code_viewer", NonFocusTextArea).border_title = (
            "Emitted Target Assembly Code (Full Stream)"
        )
        self.update_ui()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            phase = event.item.id.replace("item_", "")
            self.session.select_phase(phase)
            self.update_ui()

    def action_next_frame(self) -> None:
        if self.session.next_step():
            self.update_ui()

    def action_prev_frame(self) -> None:
        if self.session.prev_step():
            self.update_ui()

    def action_first_frame(self) -> None:
        self.session.jump_to_start()
        self.update_ui()

    def action_last_frame(self) -> None:
        self.session.jump_to_end()
        self.update_ui()

    def action_show_output_info(self) -> None:
        self.notify(
            "Full compilation outputs are generated in the './output/' folder.",
            title="Outputs Generated",
            severity="info",
        )

    def update_ui(self) -> None:
        phase = self.session.current_phase
        frame_idx = self.session.frame_index
        capture = self.session.captures.get(phase) if phase else None

        if not capture:
            self.query_one("#assembly_code_viewer", NonFocusTextArea).display = False
            self.query_one("#step_info", Static).update(
                Panel(
                    Text.assemble(
                        ("[Skipped] ", "bold red"),
                        (
                            f"Phase {self.phase_map.get(phase, phase)} was not executed",
                            "bold white",
                        ),
                    ),
                    title="Current Step Action",
                    border_style="red",
                )
            )
            self.query_one("#source_code", TextArea).text = self.session.source
            state_widget = self.query_one("#state_context_content", Static)
            state_widget.update("No active frame details (phase skipped).")
            state_widget.refresh(layout=True)
            return

        frames_count = len(capture.frames)
        frame = self.session.get_current_frame()

        # Hide or show assembly viewer based on phase
        self.query_one("#assembly_code_viewer", NonFocusTextArea).display = phase == "code_gen"

        # Update step info header
        step_title = frame.title if frame else "End of Phase"
        total_steps_str = f"Step {frame_idx + 1}/{frames_count}" if frames_count else "No Steps"
        self.query_one("#step_info", Static).update(
            Panel(
                Text.assemble((f"[{total_steps_str}] ", "bold cyan"), (step_title, "bold white")),
                title="Current Step Action",
                border_style="bright_blue",
            )
        )

        # Update source code preview using TextArea cursor tracking
        source_widget = self.query_one("#source_code", TextArea)
        line_num = None
        if frame and frame.detail:
            line_num = frame.detail.get("line")

        if line_num is not None:
            source_widget.cursor_location = (line_num - 1, 0)
        else:
            source_widget.cursor_location = (0, 0)

        # Update state context panel
        self.update_context_pane(phase, frame)
        state_widget = self.query_one("#state_context_content", Static)
        state_widget.refresh(layout=True)

        # Auto-scroll state context to track active step or bottom of container
        scroll_container = self.query_one("#state_context", ScrollableContainer)
        if phase in ("tac", "optimizer") and frame and frame.detail:
            idx = frame.detail.get("index")
            if idx is not None:
                viewport_height = scroll_container.size.height or 15
                target_line = 3 + idx * 2
                target_y = max(0, target_line - (viewport_height // 2))
                self.call_after_refresh(scroll_container.scroll_to, y=target_y, animate=False)
        else:
            self.call_after_refresh(scroll_container.scroll_end, animate=False)

    def update_context_pane(self, phase: str, frame: StepFrame | None) -> None:
        if not frame:
            self.query_one("#state_context_content", Static).update("No active frame details.")
            return

        context = frame.context
        detail = frame.detail

        if phase == "lexer":
            table = Table(
                title="Lexer Step Matches",
                show_header=True,
                header_style="bold green",
            )
            table.add_column("Property", style="dim")
            table.add_column("Value", style="bold white")
            table.add_row("Token Kind", str(detail.get("kind")))
            table.add_row("Token Value", f"'{detail.get('value')}'")
            table.add_row("Line", str(detail.get("line")))
            table.add_row("Column", str(detail.get("column")))

            errors = context.get("errors", [])
            if errors:
                err_text = "\n".join([f"• {e}" for e in errors])
                self.query_one("#state_context_content", Static).update(
                    Group(
                        table,
                        Text("\nLexical Errors:\n", style="bold red"),
                        Text(err_text),
                    )
                )
            else:
                self.query_one("#state_context_content", Static).update(table)

        elif phase == "ll1_parser":
            stack = detail.get("stack", "[]")
            lookahead = detail.get("lookahead", "$")
            action = detail.get("action", "")

            errors = context.get("semantic_errors", [])
            err_lbl = ""
            if errors:
                err_lbl = "\n[bold red]Semantic Errors:[/bold red]\n" + "\n".join(
                    [f"  • {e}" for e in errors]
                )

            msg = (
                f"{stack}\n\n"
                f"[bold green]Lookahead:[/bold green] {lookahead}\n"
                f"[bold green]Action:[/bold green] {action}{err_lbl}"
            )
            self.query_one("#state_context_content", Static).update(
                Panel(
                    msg,
                    title="LL(1) Parser Context",
                    border_style="magenta",
                )
            )

        elif phase == "slr_parser":
            stack = context.get("stack", [])
            sem_stack = context.get("semantic_stack", [])
            ctrl_stack = context.get("control_stack", [])
            action = detail.get("action", "")

            self.query_one("#state_context_content", Static).update(
                Panel(
                    f"[bold cyan]State Stack:[/bold cyan]\n  {stack}\n\n"
                    f"[bold cyan]Semantic Stack:[/bold cyan]\n  {sem_stack}\n\n"
                    f"[bold cyan]Control Stack (Backpatch):[/bold cyan]\n  {ctrl_stack}\n\n"
                    f"[bold green]Parsed Action:[/bold green] {action}",
                    title="SLR(1) Parsing Engine",
                    border_style="magenta",
                )
            )

        elif phase == "symbol_table":
            table = Table(
                title="Symbol Table Allocations",
                show_header=True,
                header_style="bold yellow",
            )
            table.add_column("Variable", style="bold yellow")
            table.add_column("Type", style="cyan")
            table.add_column("Scope Level", style="magenta")
            table.add_column("Offset", style="green")

            variables = context.get("variables", [])
            for var in variables:
                table.add_row(
                    var["name"],
                    var["type"],
                    str(var["scope"]),
                    f"{var['offset']} bytes",
                )

            next_offset = context.get("next_offset", 0)

            self.query_one("#state_context_content", Static).update(
                Group(
                    table,
                    Text(f"\nNext Offset Pointer: {next_offset} bytes", style="bold green"),
                )
            )

        elif phase == "tac":
            quads = context.get("quads", [])
            table = Table(
                title="Three-Address Code (TAC) Quads",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Index", style="dim")
            table.add_column("Op", style="bold white")
            table.add_column("Arg1", style="cyan")
            table.add_column("Arg2", style="cyan")
            table.add_column("Result", style="green")

            for idx, q in enumerate(quads):
                is_active = detail.get("index") == idx
                style = "bold white on blue" if is_active else ""
                table.add_row(str(idx), q[0], q[1], q[2], q[3], style=style)
            self.query_one("#state_context_content", Static).update(table)

        elif phase == "optimizer":
            quads = context.get("quads", [])
            table = Table(
                title="Optimized Three-Address Code",
                show_header=True,
                header_style="bold green",
            )
            table.add_column("Index", style="dim")
            table.add_column("Op", style="bold white")
            table.add_column("Arg1", style="cyan")
            table.add_column("Arg2", style="cyan")
            table.add_column("Result", style="green")

            for idx, q in enumerate(quads):
                is_active = detail.get("index") == idx
                style = "bold white on green" if is_active else ""
                table.add_row(str(idx), q[0], q[1], q[2], q[3], style=style)
            self.query_one("#state_context_content", Static).update(
                Group(
                    Text(f"Message: {detail.get('msg', '')}\n", style="bold green"),
                    table,
                )
            )

        elif phase == "code_gen":
            instructions = context.get("instructions", [])
            registers = context.get("registers", {})

            reg_table = Table(
                title="Active CPU Registers Allocator",
                show_header=True,
                header_style="bold yellow",
            )
            reg_table.add_column("Register", style="bold yellow")
            reg_table.add_column("Assigned Variable", style="cyan")
            for reg, var in sorted(registers.items()):
                reg_table.add_row(reg, var)

            # Create a 2-column layout grid to display Details Panel and Register Table side-by-side
            layout_table = Table.grid(expand=True)
            layout_table.add_column(ratio=1)
            layout_table.add_column(ratio=1)

            details_panel = Panel(
                f"[bold green]Quad under translation:[/bold green] {detail.get('quad')}\n"
                f"[bold green]Emitted Code for Quad:[/bold green]\n"
                + "\n".join([f"  {i}" for i in detail.get("generated_instructions", [])]),
                title="Code Generator Details",
                border_style="yellow",
            )

            layout_table.add_row(details_panel, reg_table)

            self.query_one("#state_context_content", Static).update(layout_table)

            full_instrs_text = "\n".join(instructions) if instructions else ""
            asm_viewer = self.query_one("#assembly_code_viewer", NonFocusTextArea)
            asm_viewer.text = full_instrs_text
            if instructions:
                asm_viewer.cursor_location = (len(instructions) - 1, 0)
