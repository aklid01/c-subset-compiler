"""
Frames module for compiler visualization.
Defines StepFrame and PhaseCapture dataclasses to hold intermediate state.
"""

from dataclasses import dataclass, field


@dataclass
class StepFrame:
    phase: str
    index: int
    title: str
    detail: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)


@dataclass
class PhaseCapture:
    name: str
    frames: list[StepFrame]
    success: bool
    final_output: list[str] = field(default_factory=list)
