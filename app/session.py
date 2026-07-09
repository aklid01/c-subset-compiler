"""
Visualizer Session module.
Manages visualizer navigation state, active compilation phase, and step frame pointers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compiler_core.frames import PhaseCapture, StepFrame

from compiler_core.pipeline import run_all_captures


class VizSession:
    """Manages the visualizer navigation state, tracking active compiler phase and step frame."""

    def __init__(self, source: str):
        self.source = source
        self.captures: dict[str, PhaseCapture] = run_all_captures(source)

        # Determine available phases
        self.phases = list(self.captures.keys())
        self.current_phase = self.phases[0] if self.phases else None
        self.frame_index = 0

    def get_phases(self) -> list[str]:
        """Return the list of phase names captured in the current session."""
        return self.phases

    def select_phase(self, phase: str) -> None:
        """Set the active phase and reset the step frame index to 0."""
        if phase not in self.captures:
            raise ValueError(f"Unknown phase: {phase}")
        self.current_phase = phase
        self.frame_index = 0

    def next_step(self) -> bool:
        """Advance to the next step in the current phase. Returns True if successful."""
        if not self.current_phase:
            return False
        capture = self.captures[self.current_phase]
        if self.frame_index < len(capture.frames) - 1:
            self.frame_index += 1
            return True
        return False

    def prev_step(self) -> bool:
        """Step back to the previous step in the current phase. Returns True if successful."""
        if self.frame_index > 0:
            self.frame_index -= 1
            return True
        return False

    def jump_to_start(self) -> None:
        """Jump to the beginning of the current phase."""
        self.frame_index = 0

    def jump_to_end(self) -> None:
        """Jump to the last step of the current phase."""
        if not self.current_phase:
            return
        capture = self.captures[self.current_phase]
        self.frame_index = max(0, len(capture.frames) - 1)

    def get_current_frame(self) -> StepFrame | None:
        """Return the current StepFrame snapshot, or None if no frames exist."""
        if not self.current_phase:
            return None
        capture = self.captures[self.current_phase]
        if 0 <= self.frame_index < len(capture.frames):
            return capture.frames[self.frame_index]
        return None
