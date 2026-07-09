import sys

from compiler_core.src.lexer import tokenize
from compiler_core.src.lr_parser import SLRParser
from compiler_core.src.parser import LL1Parser


def run_compiler(file_path):
    try:
        with open(file_path) as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return

    tokens, lex_errors = tokenize(code)

    if lex_errors:
        print("\nLexical Errors\n")
        for err in lex_errors:
            print(err)
        return

    ll1 = LL1Parser(tokens)
    ll1.display_sets()
    ll1_success = ll1.parse()

    slr = SLRParser(tokens, ll1)
    slr_success, tac = slr.parse()

    if not ll1_success or not slr_success:
        return

    ll1.symbol_table.display("LL1")
    slr.symbol_table.display("SLR")

    all_semantic_errors = ll1.semantic_errors + slr.semantic_errors

    width = 62
    if all_semantic_errors:
        print("\n" + "═" * width)
        print(" SEMANTIC ERROR REPORT ".center(width, "═"))
        print("═" * width)
        print(f"  Total errors found: {len(all_semantic_errors)}")
        print("─" * width)

        if ll1.semantic_errors:
            print(f"\n  ▸ LL(1) detected {len(ll1.semantic_errors)} error(s):\n")
            for err in ll1.semantic_errors:
                print(f"    {err}")

        if slr.semantic_errors:
            print(f"\n  ▸ SLR(1) detected {len(slr.semantic_errors)} error(s):\n")
            for err in slr.semantic_errors:
                print(f"    {err}")

        print("\n" + "═" * width)
        print(" TAC generation skipped due to semantic errors. ".center(width, "═"))
        print("═" * width + "\n")
        return

    print("\n" + "═" * width)
    print(" SEMANTIC ANALYSIS ".center(width, "═"))
    print("═" * width)
    print("  [✓] LL(1): No semantic errors detected.")
    print("  [✓] SLR(1): No semantic errors detected.")
    print("═" * width + "\n")

    if slr_success:
        tac.display()

        tac.optimize_and_generate(
            tac_path="./output/tac_output.txt",
            opt_path="./output/optimized_tac_output.txt",
            target_path="./output/target_output.txt",
        )


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "./input/input.txt"
    run_compiler(input_file)
