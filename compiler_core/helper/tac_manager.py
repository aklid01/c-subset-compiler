"""
TAC Manager module for the C-subset compiler.
Manages the generation of intermediate Three-Address Code (TAC),
providing temp/label allocation, code emission, and backpatching.
"""

import os

from compiler_core.helper.code_gen import display as cg_display
from compiler_core.helper.code_gen import generate
from compiler_core.helper.code_gen import save as cg_save
from compiler_core.helper.optimizer import optimize

_COL_W = 10


class TACManager:
    def __init__(self, capture_list: list = None):
        self.quads: list[list[str]] = []
        self.temp_count = 0
        self.label_count = 0
        self.capture_list = capture_list

    def new_temp(self) -> str:
        """Allocate a new temporary variable name."""
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self) -> str:
        """Allocate a new jump label name."""
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op: str, arg1: str, arg2: str, res: str) -> int:
        """Emit a TAC quadruple and return its index."""
        self.quads.append([op, arg1, arg2, res])
        idx = len(self.quads) - 1
        if self.capture_list is not None:
            from compiler_core.frames import StepFrame

            self.capture_list.append(
                StepFrame(
                    phase="tac",
                    index=len(self.capture_list),
                    title=f"Emit Quad: ({op}, {arg1}, {arg2}, {res})",
                    detail={"op": op, "arg1": arg1, "arg2": arg2, "res": res, "index": idx},
                    context={"quads": [list(q) for q in self.quads]},
                )
            )
        return idx

    def backpatch(self, quad_index: int, target_label: str) -> None:
        """Backpatch the target label of a previously emitted pending quad."""
        self.quads[quad_index][3] = target_label
        if self.capture_list is not None:
            from compiler_core.frames import StepFrame

            self.capture_list.append(
                StepFrame(
                    phase="tac",
                    index=len(self.capture_list),
                    title=f"Backpatch Quad {quad_index} with {target_label}",
                    detail={"index": quad_index, "label": target_label},
                    context={"quads": [list(q) for q in self.quads]},
                )
            )

    def _header(self):
        sep = "─" * (8 + 1 + (_COL_W + 3) * 4)
        header = (
            f"{'Index':<8}| {'Op':<{_COL_W}}| {'Arg1':<{_COL_W}}"
            f"| {'Arg2':<{_COL_W}}| {'Result':<{_COL_W}}"
        )
        return header, sep

    def _row(self, i, q):
        return (
            f"{i:<8}| {str(q[0]):<{_COL_W}}| {str(q[1]):<{_COL_W}}"
            f"| {str(q[2]):<{_COL_W}}| {str(q[3]):<{_COL_W}}"
        )

    def _lines(self, quads: list[list[str]] = None) -> list[str]:
        if quads is None:
            quads = self.quads
        header, sep = self._header()
        rows = [self._row(i, q) for i, q in enumerate(quads)]
        return [header, sep] + rows

    def display(self) -> None:
        """Display the Three-Address Code (TAC) quadruples on the console."""
        print("\n" + "═" * 60)
        print(" THREE-ADDRESS CODE  (Quadruples) ".center(60, "═"))
        print("═" * 60)
        for line in self._lines(self.quads):
            print(line)
        print("═" * 60)
        print(f"  Total quads : {len(self.quads)}")
        print(f"  Temporaries : {self.temp_count}")
        print(f"  Labels      : {self.label_count}")
        print("═" * 60 + "\n")

    def save(self, path: str = "./output/tac_output.txt") -> None:
        """Save the Three-Address Code (TAC) quadruples to a text file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("THREE-ADDRESS CODE  (Quadruples)\n")
            f.write("=" * 60 + "\n")
            for line in self._lines(self.quads):
                f.write(line + "\n")
            f.write("=" * 60 + "\n")
            f.write(f"Total quads : {len(self.quads)}\n")
            f.write(f"Temporaries : {self.temp_count}\n")
            f.write(f"Labels      : {self.label_count}\n")
        print(f"[Success] TAC written to {path}")

    def optimize_and_generate(
        self,
        tac_path: str = "./output/tac_output.txt",
        opt_path: str = "./output/optimized_tac_output.txt",
        target_path: str = "./output/target_output.txt",
    ) -> None:
        """Optimize TAC and generate final target code representation."""
        self.save(tac_path)

        opt_quads, report = optimize(self.quads)
        print(report)

        width = 60
        print("\n" + "═" * width)
        print(" OPTIMIZED THREE-ADDRESS CODE  (Quadruples) ".center(width, "═"))
        print("═" * width)
        opt_lines = self._lines(opt_quads)
        for line in opt_lines:
            print(line)
        print("═" * width)
        print(f"  Total quads : {len(opt_quads)}")
        print("═" * width + "\n")

        os.makedirs(os.path.dirname(opt_path), exist_ok=True)
        with open(opt_path, "w", encoding="utf-8") as f:
            f.write("OPTIMIZED THREE-ADDRESS CODE  (Quadruples)\n")
            f.write("=" * 60 + "\n")
            for line in opt_lines:
                f.write(line + "\n")
            f.write("=" * 60 + "\n")
            f.write(f"Total quads : {len(opt_quads)}\n")
        print(f"[Success] Optimized TAC written to {opt_path}")

        instrs = generate(opt_quads)
        cg_display(instrs)
        cg_save(instrs, target_path)
