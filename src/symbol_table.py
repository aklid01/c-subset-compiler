class Symbol:
    def __init__(self, name, data_type, scope_level, offset):
        self.name = name
        self.data_type = data_type
        self.scope_level = scope_level
        self.offset = offset

    def __repr__(self):
        return f"[{self.data_type} | Scope:{self.scope_level} | Offset:{self.offset}]"


class SymbolTable:
    def __init__(self):
        self.scopes = [{}]
        self.history = []
        self.log = []
        self.current_scope_level = 0
        self.next_offset = 0

    def enter_scope(self):
        self.scopes.append({})
        self.current_scope_level += 1
        self.log.append(f"--- Entering Scope Level {self.current_scope_level} ---")

    def exit_scope(self):
        if self.current_scope_level > 0:
            self.log.append(
                f"--- Exiting to Scope Level {self.current_scope_level-1} ---"
            )
            self.scopes.pop()
            self.current_scope_level -= 1

    def insert(self, name, data_type):
        if name in self.scopes[-1]:
            return False
        size = 8 if data_type.upper() == "FLOAT" else 4

        new_symbol = Symbol(name, data_type, self.current_scope_level, self.next_offset)
        self.scopes[-1][name] = new_symbol
        self.history.append((name, new_symbol))

        self.log.append(f"Allocating {name} ({data_type}) at offset {self.next_offset}")
        self.next_offset += size
        return True

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def display(self, parser_name):
        print("\n" + "═" * 60)
        print(f" {parser_name} SYMBOL TABLE REPORT ".center(60, "═"))
        print("═" * 60)
        print("\n▣ STEP-BY-STEP UPDATES")
        print("─" * 40)
        for entry in self.log:
            if "Level 1" in entry or "Level 2" in entry:
                print(f"  ▸ {entry}")
            else:
                print(f"  • {entry}")
        print("\n▣ FINAL ATTRIBUTE SUMMARY")
        print("─" * 60)
        header = f"{'Variable':<12} | {'Type':<10} | {'Scope':<8} | {'Offset':<8}"
        print(header)
        print("-" * 60)

        for name, sym in self.history:
            print(
                f"{name:<12} | {sym.data_type:<10} | {sym.scope_level:<8} | {sym.offset:<8}"
            )

        print("─" * 60)
        print(f"Total Stack Memory Reserved: {self.next_offset} bytes")
        print("═" * 60 + "\n")
        print(f"[Success] {parser_name} symbol table generated.")
