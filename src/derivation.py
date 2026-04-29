def leftmost_derivation():

    print("\nLEFTMOST DERIVATION\n")

    steps = [
        "AssignStmt",
        "ID = Expr ;",
        "sum = Expr ;",
        "sum = Expr + Term ;",
        "sum = Term + Term ;",
        "sum = ID + Term ;",
        "sum = sum + Term ;",
        "sum = sum + ID ;",
        "sum = sum + temp ;",
    ]

    for s in steps:
        print("→", s)


def rightmost_derivation():

    print("\nRIGHTMOST DERIVATION\n")

    steps = [
        "AssignStmt",
        "ID = Expr ;",
        "ID = Expr + Term ;",
        "ID = Expr + ID ;",
        "ID = Expr + temp ;",
        "ID = Term + temp ;",
        "ID = ID + temp ;",
        "ID = sum + temp ;",
        "sum = sum + temp ;",
    ]

    for s in steps:
        print("→", s)
