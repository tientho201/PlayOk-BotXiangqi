def matrix_to_fen(board_matrix, active_color="w"):
    """
    Converts a 10x9 board pieces matrix into a standard Xiangqi FEN string.
    board_matrix: A 10x9 grid of piece characters (Red: UPPERCASE, Black: lowercase, Empty: '.')
    active_color: 'w' (Red/White - standard in UCI engines) or 'b' (Black)
    """
    if not board_matrix or len(board_matrix) != 10:
        return ""
        
    fen_rows = []
    for row in board_matrix:
        empty_count = 0
        row_fen = ""
        for cell in row:
            if cell == ".":
                empty_count += 1
            else:
                if empty_count > 0:
                    row_fen += str(empty_count)
                    empty_count = 0
                row_fen += cell
        if empty_count > 0:
            row_fen += str(empty_count)
        fen_rows.append(row_fen)
        
    board_fen = "/".join(fen_rows)
    
    # Standard Xiangqi UCI FEN format fields:
    # 1. Piece placement
    # 2. Active color ('w' for Red/White, 'b' for Black)
    # 3. Castling rights (always '-' for Xiangqi)
    # 4. En passant target square (always '-' for Xiangqi)
    # 5. Halfmove clock (moves since last capture or pawn advance)
    # 6. Fullmove number
    return f"{board_fen} {active_color} - - 0 1"
