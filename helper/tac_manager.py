import os
from helper.optimizer import optimize
from helper.code_gen import generate, display as cg_display, save as cg_save

_COL_W = 10


class TACManager:
    def __init__(self):
        self.quads = []
        self.temp_count = 0
        self.label_count = 0

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op, arg1, arg2, res):
        self.quads.append([op, arg1, arg2, res])
        return len(self.quads) - 1

    def backpatch(self, quad_index, target_label):
        self.quads[quad_index][3] = target_label

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

    def _lines(self):
        header, sep = self._header()
        rows = [self._row(i, q) for i, q in enumerate(self.quads)]
        return [header, sep] + rows

    def display(self):
        print("\n" + "═" * 60)
        print(" THREE-ADDRESS CODE  (Quadruples) ".center(60, "═"))
        print("═" * 60)
        for line in self._lines():
            print(line)
        print("═" * 60)
        print(f"  Total quads : {len(self.quads)}")
        print(f"  Temporaries : {self.temp_count}")
        print(f"  Labels      : {self.label_count}")
        print("═" * 60 + "\n")

    def save(self, path="./output/tac_output.txt"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("THREE-ADDRESS CODE  (Quadruples)\n")
            f.write("=" * 60 + "\n")
            for line in self._lines():
                f.write(line + "\n")
            f.write("=" * 60 + "\n")
            f.write(f"Total quads : {len(self.quads)}\n")
            f.write(f"Temporaries : {self.temp_count}\n")
            f.write(f"Labels      : {self.label_count}\n")
        print(f"[Success] TAC written to {path}")

    def optimize_and_generate(
        self,
        tac_path="./output/tac_output.txt",
        opt_path="./output/optimized_tac_output.txt",
        target_path="./output/target_output.txt",
    ):
        self.save(tac_path)

        opt_quads, report = optimize(self.quads)
        print(report)

        width = 60
        print("\n" + "═" * width)
        print(" OPTIMIZED THREE-ADDRESS CODE  (Quadruples) ".center(width, "═"))
        print("═" * width)
        header = (
            f"{'Index':<8}| {'Op':<{_COL_W}}| {'Arg1':<{_COL_W}}"
            f"| {'Arg2':<{_COL_W}}| {'Result':<{_COL_W}}"
        )
        sep = "─" * (8 + 1 + (_COL_W + 3) * 4)
        print(header)
        print(sep)
        for i, q in enumerate(opt_quads):
            print(
                f"{i:<8}| {str(q[0]):<{_COL_W}}| {str(q[1]):<{_COL_W}}"
                f"| {str(q[2]):<{_COL_W}}| {str(q[3]):<{_COL_W}}"
            )
        print("═" * width)
        print(f"  Total quads : {len(opt_quads)}")
        print("═" * width + "\n")

        os.makedirs(os.path.dirname(opt_path), exist_ok=True)
        with open(opt_path, "w", encoding="utf-8") as f:
            f.write("OPTIMIZED THREE-ADDRESS CODE  (Quadruples)\n")
            f.write("=" * 60 + "\n")
            f.write(header + "\n")
            f.write(sep + "\n")
            for i, q in enumerate(opt_quads):
                f.write(
                    f"{i:<8}| {str(q[0]):<{_COL_W}}| {str(q[1]):<{_COL_W}}"
                    f"| {str(q[2]):<{_COL_W}}| {str(q[3]):<{_COL_W}}\n"
                )
            f.write("=" * 60 + "\n")
            f.write(f"Total quads : {len(opt_quads)}\n")
        print(f"[Success] Optimized TAC written to {opt_path}")

        instrs = generate(opt_quads)
        cg_display(instrs)
        cg_save(instrs, target_path)
