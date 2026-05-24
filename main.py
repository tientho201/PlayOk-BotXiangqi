import sys
import os
import json
import time
import math
import re
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QSlider, QRadioButton, QButtonGroup, 
    QTextEdit, QFrame, QMessageBox, QFileDialog, QMenu
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter, QPen, QBrush
from screen_capture import capture_screen_area
from piece_detector import PieceDetector
from overlay import XiangqiOverlay
from fen_converter import matrix_to_fen
from pikafish_engine import PikafishEngine
from board_calibrator import BoardCalibrator

def parse_uci_move(move_str):
    """
    Parses a UCI move string (like 'd10d1' or 'a1a2') from Fairy-Stockfish/Pikafish.
    Returns (col_from, row_from, col_to, row_to) as 0-indexed matrix coordinates (col: 0..8, row: 0..9).
    """
    match = re.match(r"^([a-i])(10|[1-9])([a-i])(10|[1-9])$", move_str.lower())
    if not match:
        return None
    c1_char, r1_str, c2_char, r2_str = match.groups()
    c1 = ord(c1_char) - ord('a')
    c2 = ord(c2_char) - ord('a')
    r1 = 10 - int(r1_str)
    r2 = 10 - int(r2_str)
    return c1, r1, c2, r2

# Visual piece mapping to traditional Chinese characters
PIECE_CHAR_MAP = {
    "K": "帥", "A": "仕", "B": "相", "R": "俥", "N": "傌", "C": "炮", "P": "兵",
    "k": "將", "a": "士", "b": "象", "r": "車", "n": "馬", "c": "砲", "p": "卒"
}

# Standard initial setup board matrix
STARTING_MATRIX = [
    ["r", "n", "b", "a", "k", "a", "b", "n", "r"],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", "c", ".", ".", ".", ".", ".", "c", "."],
    ["p", ".", "p", ".", "p", ".", "p", ".", "p"],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    ["P", ".", "P", ".", "P", ".", "P", ".", "P"],
    [".", "C", ".", ".", ".", ".", ".", "C", "."],
    [".", ".", ".", ".", ".", ".", ".", ".", "."],
    ["R", "N", "B", "A", "K", "A", "B", "N", "R"]
]

class VirtualBoardWidget(QWidget):
    """
    Stunning, interactive 10x9 Chinese Chess board widget.
    Displays active pieces in traditional red/slate circular tokens with SimSun font.
    Allows the user to drag, drop, add, or remove pieces manually on this local grid at any time.
    """
    board_changed = pyqtSignal(list)  # Emits the updated 10x9 board matrix

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(580, 580)
        self.board_matrix = [row[:] for row in STARTING_MATRIX]
        self.selected_sq = None  # Holds active selection (row, col)
        self.bestmove = None

        # Drag and drop state
        self.dragging_piece = None
        self.drag_start_sq = None
        self.drag_current_pos = None

        # Selected placement tool
        self.placement_tool = None

    def set_placement_tool(self, tool):
        """Sets the active piece placement tool ('K', 'r', 'eraser', etc. or None)."""
        self.placement_tool = tool
        self.selected_sq = None
        self.update()

    def set_board(self, matrix):
        """Sets the board state and clears previous selection highlights."""
        self.board_matrix = [row[:] for row in matrix]
        self.selected_sq = None
        self.update()

    def get_board(self):
        return self.board_matrix

    def set_bestmove(self, bestmove):
        """Sets the bestmove string to draw an arrow on the virtual board too."""
        self.bestmove = bestmove
        self.update()

    def clear_bestmove(self):
        self.bestmove = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Board grid padding margins
        margin_x = 22
        margin_y = 22
        col_width = (w - 2 * margin_x) / 8.0
        row_height = (h - 2 * margin_y) / 9.0

        # Paint gorgeous background slate card
        painter.fillRect(self.rect(), QColor(30, 32, 35))

        # Paint outer dark border grid
        border_pen = QPen(QColor(80, 85, 90), 2)
        painter.setPen(border_pen)
        painter.drawRect(margin_x - 4, margin_y - 4, int(w - 2 * margin_x + 8), int(h - 2 * margin_y + 8))

        # Paint standard intersections grid lines
        grid_pen = QPen(QColor(60, 65, 70), 1)
        painter.setPen(grid_pen)

        # 1. Paint vertical columns (omitted at river space)
        for col in range(9):
            x = int(margin_x + col * col_width)
            # Top side
            painter.drawLine(x, margin_y, x, int(margin_y + 4 * row_height))
            # Bottom side
            painter.drawLine(x, int(margin_y + 5 * row_height), x, h - margin_y)
            # Outer edges pass through river
            if col == 0 or col == 8:
                painter.drawLine(x, int(margin_y + 4 * row_height), x, int(margin_y + 5 * row_height))

        # 2. Paint horizontal rows
        for row in range(10):
            y = int(margin_y + row * row_height)
            painter.drawLine(margin_x, y, w - margin_x, y)

        # 3. Paint Palace Diagonals (X marks)
        # Top Palace (cols 3-5, rows 0-2)
        x3 = int(margin_x + 3 * col_width)
        x5 = int(margin_x + 5 * col_width)
        y0 = margin_y
        y2 = int(margin_y + 2 * row_height)
        painter.drawLine(x3, y0, x5, y2)
        painter.drawLine(x5, y0, x3, y2)

        # Bottom Palace (cols 3-5, rows 7-9)
        y7 = int(margin_y + 7 * row_height)
        y9 = h - margin_y
        painter.drawLine(x3, y7, x5, y9)
        painter.drawLine(x5, y7, x3, y9)

        # 4. Draw river text: "SỞ HÀ" (left) & "HÁN GIỚI" (right)
        painter.setPen(QColor(95, 100, 110, 110))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        y_river = int(margin_y + 4.5 * row_height)
        painter.drawText(int(margin_x + 1.2 * col_width), y_river + 5, "SỞ HÀ")
        painter.drawText(int(margin_x + 5.2 * col_width), y_river + 5, "HÁN GIỚI")

        # 5. Draw active selection ring (only if not currently dragging that piece)
        if self.selected_sq and (not self.dragging_piece or self.drag_start_sq != self.selected_sq):
            r_sel, c_sel = self.selected_sq
            x_sel = int(margin_x + c_sel * col_width)
            y_sel = int(margin_y + r_sel * row_height)
            painter.setPen(QPen(QColor(255, 69, 0), 2))
            painter.setBrush(QBrush(QColor(255, 69, 0, 45)))
            painter.drawEllipse(QPoint(x_sel, y_sel), 16, 16)

        # 6. Render pieces
        r_circ = int(min(col_width, row_height) * 0.40)
        for row in range(10):
            for col in range(9):
                piece = self.board_matrix[row][col]
                if piece != ".":
                    cx = int(margin_x + col * col_width)
                    cy = int(margin_y + row * row_height)

                    is_dragging_this = (self.dragging_piece and self.drag_start_sq == (row, col))
                    if is_dragging_this:
                        # Draw faint dotted placeholder at source square
                        painter.setPen(QPen(QColor(120, 120, 120, 100), 1, Qt.DashLine))
                        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
                        painter.drawEllipse(QPoint(cx, cy), r_circ, r_circ)
                        continue

                    is_red = piece.isupper()
                    bg_color = QColor(195, 40, 30) if is_red else QColor(44, 48, 56)
                    border_color = QColor(235, 75, 65) if is_red else QColor(75, 80, 90)
                    text_color = QColor(255, 255, 255)

                    # Draw circular piece tokens
                    if self.selected_sq == (row, col):
                        # Glow selected border cyan
                        painter.setPen(QPen(QColor(0, 238, 255), 3))
                    else:
                        painter.setPen(QPen(border_color, 2))

                    painter.setBrush(QBrush(bg_color))
                    painter.drawEllipse(QPoint(cx, cy), r_circ, r_circ)

                    # Paint elegant inner rim groove
                    painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPoint(cx, cy), r_circ - 3, r_circ - 3)

                    # Paint standard SimSun Chinese character in the center
                    painter.setPen(text_color)
                    # Dynamically scale font size to circle bounds
                    painter.setFont(QFont("SimSun", int(r_circ * 0.95), QFont.Bold))
                    char_str = PIECE_CHAR_MAP.get(piece, "?")

                    # Draw text perfectly centered inside the circular token bounding rect
                    rect_text = QRect(cx - r_circ, cy - r_circ, 2 * r_circ, 2 * r_circ)
                    painter.drawText(rect_text, Qt.AlignCenter, char_str)

        # 7. Render currently dragged piece centered at the mouse coordinates
        if self.dragging_piece and self.drag_current_pos:
            cx = self.drag_current_pos.x()
            cy = self.drag_current_pos.y()
            is_red = self.dragging_piece.isupper()
            bg_color = QColor(195, 40, 30, 220)  # Slightly translucent
            border_color = QColor(235, 75, 65, 220)
            text_color = QColor(255, 255, 255, 220)

            painter.setPen(QPen(border_color, 2))
            painter.setBrush(QBrush(bg_color))
            painter.drawEllipse(QPoint(cx, cy), r_circ, r_circ)

            painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(cx, cy), r_circ - 3, r_circ - 3)

            painter.setPen(text_color)
            painter.setFont(QFont("SimSun", int(r_circ * 0.95), QFont.Bold))
            char_str = PIECE_CHAR_MAP.get(self.dragging_piece, "?")
            rect_text = QRect(cx - r_circ, cy - r_circ, 2 * r_circ, 2 * r_circ)
            painter.drawText(rect_text, Qt.AlignCenter, char_str)

        # 8. Draw recommended bestmove arrow on virtual board too
        if self.bestmove and len(self.bestmove) >= 4:
            try:
                parsed = parse_uci_move(self.bestmove)
                if parsed:
                    c1, r1, c2, r2 = parsed
                    x1 = int(margin_x + c1 * col_width)
                    y1 = int(margin_y + r1 * row_height)
                    x2 = int(margin_x + c2 * col_width)
                    y2 = int(margin_y + r2 * row_height)

                    # Draw glowing Cyan path arrow line
                    pen_arrow = QPen(QColor(0, 238, 255, 200), 3, Qt.SolidLine, Qt.RoundCap)
                    painter.setPen(pen_arrow)
                    painter.drawLine(x1, y1, x2, y2)

                    # Draw target landing dot
                    painter.setPen(QPen(QColor(0, 255, 127), 2))
                    painter.setBrush(QBrush(QColor(0, 255, 127, 200)))
                    painter.drawEllipse(QPoint(x2, y2), 5, 5)
            except Exception:
                pass

    def mousePressEvent(self, event):
        w = self.width()
        h = self.height()
        margin_x = 22
        margin_y = 22
        col_width = (w - 2 * margin_x) / 8.0
        row_height = (h - 2 * margin_y) / 9.0

        x = event.x()
        y = event.y()

        # Find closest grid intersection coordinates
        col = int(round((x - margin_x) / col_width))
        row = int(round((y - margin_y) / row_height))

        # Clamp bounds
        col = max(0, min(8, col))
        row = max(0, min(9, row))

        # Distance threshold (max 22px from intersection)
        cx = int(margin_x + col * col_width)
        cy = int(margin_y + row * row_height)
        if math.hypot(x - cx, y - cy) > 22:
            return

        if event.button() == Qt.LeftButton:
            if self.placement_tool is not None:
                if self.placement_tool == "eraser":
                    self.board_matrix[row][col] = "."
                else:
                    self.board_matrix[row][col] = self.placement_tool
                self.board_changed.emit(self.board_matrix)
                self.update()
                return

            current_piece = self.board_matrix[row][col]

            if current_piece != ".":
                # Start drag
                self.dragging_piece = current_piece
                self.drag_start_sq = (row, col)
                self.drag_current_pos = event.pos()
                self.selected_sq = (row, col)
            else:
                if self.selected_sq:
                    r_from, c_from = self.selected_sq
                    piece_from = self.board_matrix[r_from][c_from]
                    # Perform the move
                    if (r_from, c_from) != (row, col):
                        self.board_matrix[row][col] = piece_from
                        self.board_matrix[r_from][c_from] = "."
                        self.board_changed.emit(self.board_matrix)
                    self.selected_sq = None

            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging_piece:
            self.drag_current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging_piece:
            w = self.width()
            h = self.height()
            margin_x = 22
            margin_y = 22
            col_width = (w - 2 * margin_x) / 8.0
            row_height = (h - 2 * margin_y) / 9.0

            x = event.x()
            y = event.y()

            # Find closest grid intersection coordinates
            col = int(round((x - margin_x) / col_width))
            row = int(round((y - margin_y) / row_height))

            # Clamp bounds
            col = max(0, min(8, col))
            row = max(0, min(9, row))

            cx = int(margin_x + col * col_width)
            cy = int(margin_y + row * row_height)

            if math.hypot(x - cx, y - cy) <= 22:
                r_from, c_from = self.drag_start_sq
                if (r_from, c_from) != (row, col):
                    self.board_matrix[row][col] = self.dragging_piece
                    self.board_matrix[r_from][c_from] = "."
                    self.board_changed.emit(self.board_matrix)
                    self.selected_sq = None

            self.dragging_piece = None
            self.drag_start_sq = None
            self.drag_current_pos = None
            self.update()

    def contextMenuEvent(self, event):
        w = self.width()
        h = self.height()
        margin_x = 22
        margin_y = 22
        col_width = (w - 2 * margin_x) / 8.0
        row_height = (h - 2 * margin_y) / 9.0

        x = event.x()
        y = event.y()

        col = int(round((x - margin_x) / col_width))
        row = int(round((y - margin_y) / row_height))

        col = max(0, min(8, col))
        row = max(0, min(9, row))

        cx = int(margin_x + col * col_width)
        cy = int(margin_y + row * row_height)
        if math.hypot(x - cx, y - cy) > 24:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #242629;
                color: #fffffe;
                border: 1px solid #34373c;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #7f5af0;
            }
        """)

        current_piece = self.board_matrix[row][col]

        if current_piece != ".":
            remove_action = menu.addAction(f"Xóa quân '{PIECE_CHAR_MAP.get(current_piece, current_piece)}'")
            def make_remove_callback(r, c):
                return lambda: self.remove_piece_at(r, c)
            remove_action.triggered.connect(make_remove_callback(row, col))
            menu.addSeparator()

        red_menu = menu.addMenu("Đặt quân Đỏ...")
        black_menu = menu.addMenu("Đặt quân Đen...")

        red_pieces = [
            ("K", "Tướng (帥)"), ("A", "Sĩ (仕)"), ("B", "Tượng (相)"), 
            ("R", "Xe (俥)"), ("N", "Mã (傌)"), ("C", "Pháo (炮)"), ("P", "Tốt (兵)")
        ]
        black_pieces = [
            ("k", "Tướng (將)"), ("a", "Sĩ (士)"), ("b", "Tượng (象)"), 
            ("r", "Xe (車)"), ("n", "Mã (馬)"), ("c", "Pháo (砲)"), ("p", "Tốt (卒)")
        ]

        def make_set_callback(r, c, p_code):
            return lambda: self.set_piece_at(r, c, p_code)

        for p_code, p_name in red_pieces:
            act = red_menu.addAction(p_name)
            act.triggered.connect(make_set_callback(row, col, p_code))

        for p_code, p_name in black_pieces:
            act = black_menu.addAction(p_name)
            act.triggered.connect(make_set_callback(row, col, p_code))

        menu.exec_(event.globalPos())

    def remove_piece_at(self, row, col):
        self.board_matrix[row][col] = "."
        self.selected_sq = None
        self.board_changed.emit(self.board_matrix)
        self.update()

    def set_piece_at(self, row, col, piece_code):
        self.board_matrix[row][col] = piece_code
        self.selected_sq = None
        self.board_changed.emit(self.board_matrix)
        self.update()


class EngineWorker(QThread):
    """
    Background worker thread to run Pikafish UCI analysis.
    Prevents the main PyQt5 UI thread from blocking or lagging.
    """
    completed = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, engine, fen, depth):
        super().__init__()
        self.engine = engine
        self.fen = fen
        self.depth = depth

    def run(self):
        try:
            result = self.engine.analyze(self.fen, self.depth)
            self.completed.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class XiangqiCoachApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Xiangqi Coach - PlayOK")
        self.setMinimumSize(1000, 720)
        self.resize(1080, 780)
        
        # State variables
        self.config = {
            "bbox": None,
            "depth": 10,
            "margin_ratio": 0.045,
            "engine_path": "pikafish.exe"
        }
        self.engine = None
        self.detector = PieceDetector()
        self.overlay = XiangqiOverlay()
        self.previous_fen = ""
        self.is_scanning = False
        self.is_tracking = False
        self.reference_cells = None
        
        # Load local settings configuration
        self.load_config()
        
        # Set up modern charcoal aesthetic dark stylesheet
        self.setup_styles()
        
        # Build Sleek Dashboard Layout
        self.init_ui()
        
        # Background processing timer (Interval: 1 Second)
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.process_frame)
        
        # Calibrator visual fade timer
        self.calibration_grid_timer = QTimer(self)
        self.calibration_grid_timer.setSingleShot(True)
        self.calibration_grid_timer.timeout.connect(self.hide_calibration_grid)
        
        # Periodic background full autoresync timer (Runs every 2 seconds)
        self.resync_timer = QTimer(self)
        self.resync_timer.timeout.connect(self.autoresync_board)
        
        # Initialize overlay window position if coordinate bounds already exist
        if self.config["bbox"]:
            self.overlay.set_region(self.config["bbox"], self.config["margin_ratio"])

        # Sync the visual board with starting matrix initially
        self.board_widget.set_board(STARTING_MATRIX)

    def load_config(self):
        """Loads calibration configuration from config.json."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"Lỗi đọc config.json: {e}")

    def save_config(self):
        """Saves active configuration to config.json."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Lỗi ghi config.json: {e}")

    def setup_styles(self):
        """Applies elegant premium dark theme styles to all widgets."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #16161a;
            }
            QWidget {
                color: #fffffe;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            }
            QLabel {
                font-size: 13px;
            }
            QFrame#card {
                background-color: #242629;
                border-radius: 12px;
                border: 1px solid #34373c;
            }
            QPushButton {
                background-color: #7f5af0;
                color: #fffffe;
                font-weight: bold;
                font-size: 12px;
                border: none;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #9475f3;
            }
            QPushButton:pressed {
                background-color: #6e4be3;
            }
            QPushButton:disabled {
                background-color: #444649;
                color: #949699;
            }
            QPushButton#btn-danger {
                background-color: #ff5c5c;
            }
            QPushButton#btn-danger:hover {
                background-color: #ff7575;
            }
            QPushButton#btn-danger:pressed {
                background-color: #e04c4c;
            }
            QPushButton#btn-select {
                background-color: #02c39a;
            }
            QPushButton#btn-select:hover {
                background-color: #05d9ab;
            }
            QPushButton#btn-select:pressed {
                background-color: #00ab85;
            }
            QPushButton#btn-secondary {
                background-color: #444649;
                border: 1px solid #55575a;
            }
            QPushButton#btn-secondary:hover {
                background-color: #55575a;
            }
            QRadioButton {
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #94a1b2;
            }
            QRadioButton::indicator:checked {
                background-color: #7f5af0;
                border: 2px solid #7f5af0;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #444649;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #7f5af0;
                width: 18px;
                height: 18px;
                margin-top: -6px;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #9475f3;
            }
            QTextEdit {
                background-color: #16161a;
                border: 1px solid #34373c;
                border-radius: 6px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                color: #2cb67d;
                padding: 4px;
            }
        """)

    def init_ui(self):
        """Constructs the dashboard sections with a premium two-column widescreen layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Two-Column Root Layout (Horizontal split)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Left Column: Header (Title, Status) + Large Virtual Board Widget
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Header Row
        header_layout = QHBoxLayout()
        title_label = QLabel("XIANGQI COACH")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setStyleSheet("color: #fffffe; letter-spacing: 1px;")
        
        self.status_badge = QLabel("Chưa kích hoạt")
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedSize(110, 24)
        self.status_badge.setStyleSheet("""
            background-color: #ff5c5c; 
            border-radius: 12px; 
            font-size: 11px; 
            font-weight: bold; 
            color: #fffffe;
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        left_layout.addLayout(header_layout)

        # 2. Virtual Board Card Widget (Center stage, expands)
        board_card = QFrame()
        board_card.setObjectName("card")
        board_layout = QVBoxLayout(board_card)
        board_layout.setContentsMargins(10, 10, 10, 10)
        
        # Add visual interactive board
        self.board_widget = VirtualBoardWidget(self)
        self.board_widget.board_changed.connect(self.on_virtual_board_changed)
        board_layout.addWidget(self.board_widget)
        
        left_layout.addWidget(board_card)
        main_layout.addWidget(left_widget, stretch=3)

        # Right Column: Slick Controls Panel Sidebar
        right_widget = QWidget()
        right_widget.setFixedWidth(330)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 3. Dynamic Controls Panel Card
        ctrl_card = QFrame()
        ctrl_card.setObjectName("card")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        ctrl_layout.setSpacing(10)

        # Row 1: Scan area and toggles
        row1_layout = QHBoxLayout()
        self.btn_select = QPushButton("Chọn Bàn Cờ")
        self.btn_select.setObjectName("btn-select")
        self.btn_select.clicked.connect(self.select_board_region)
        
        self.btn_sync = QPushButton("Đồng Bộ (Sync 1L)")
        self.btn_sync.clicked.connect(self.sync_board_once)
        
        self.btn_start = QPushButton("Bắt Đầu Theo Dõi")
        self.btn_start.clicked.connect(self.start_coaching)
        
        self.btn_stop = QPushButton("Dừng Theo Dõi")
        self.btn_stop.setObjectName("btn-danger")
        self.btn_stop.clicked.connect(self.stop_coaching)
        self.btn_stop.setEnabled(False)

        row1_layout.addWidget(self.btn_select)
        row1_layout.addWidget(self.btn_sync)
        row1_layout.addWidget(self.btn_start)
        row1_layout.addWidget(self.btn_stop)
        ctrl_layout.addLayout(row1_layout)

        # Row 2: Board manipulators
        row2_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Đặt Lại Bàn Cờ")
        self.btn_reset.setObjectName("btn-secondary")
        self.btn_reset.clicked.connect(self.reset_board_matrix)
        
        self.btn_clear = QPushButton("Xoá Bàn Cờ")
        self.btn_clear.setObjectName("btn-secondary")
        self.btn_clear.clicked.connect(self.clear_board_matrix)

        self.btn_resync = QPushButton("Force Resync")
        self.btn_resync.setObjectName("btn-secondary")
        self.btn_resync.clicked.connect(self.pause_coaching_for_resync)
        
        row2_layout.addWidget(self.btn_reset)
        row2_layout.addWidget(self.btn_clear)
        row2_layout.addWidget(self.btn_resync)
        ctrl_layout.addLayout(row2_layout)

        # Geometry coordinate label info
        self.lbl_geometry = QLabel("Khung toạ độ: Chưa xác định")
        self.lbl_geometry.setStyleSheet("color: #94a1b2; font-size: 11px;")
        if self.config["bbox"]:
            b = self.config["bbox"]
            self.lbl_geometry.setText(f"Khung toạ độ: {b[2]}x{b[3]} tại ({b[0]}, {b[1]})")
        ctrl_layout.addWidget(self.lbl_geometry)
        
        right_layout.addWidget(ctrl_card)

        # 3b. Visual Piece Palette Card
        palette_card = QFrame()
        palette_card.setObjectName("card")
        palette_layout = QVBoxLayout(palette_card)
        palette_layout.setContentsMargins(12, 12, 12, 12)
        palette_layout.setSpacing(8)

        pal_title = QLabel("Thêm/Xóa Quân Cờ (Palette)")
        pal_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        palette_layout.addWidget(pal_title)

        # Red pieces row
        red_flow = QHBoxLayout()
        red_flow.setSpacing(6)
        
        # Black pieces row
        black_flow = QHBoxLayout()
        black_flow.setSpacing(6)
        
        # Utility row (Eraser, Normal/Cancel)
        util_flow = QHBoxLayout()
        util_flow.setSpacing(8)

        self.palette_buttons = {}

        # Styled pieces configurations
        red_pieces_conf = [
            ("K", "帥"), ("A", "仕"), ("B", "相"), ("R", "俥"), ("N", "傌"), ("C", "炮"), ("P", "兵")
        ]
        black_pieces_conf = [
            ("k", "將"), ("a", "士"), ("b", "象"), ("r", "車"), ("n", "馬"), ("c", "砲"), ("p", "卒")
        ]

        def select_tool_callback(piece_code):
            return lambda: self.on_palette_selected(piece_code)

        for p_code, p_char in red_pieces_conf:
            btn = QPushButton(p_char)
            btn.setFixedSize(32, 32)
            btn.setFont(QFont("SimSun", 12, QFont.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #c3281e;
                    color: #ffffff;
                    border: 2px solid #eb4b41;
                    border-radius: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #e03228;
                }
            """)
            btn.clicked.connect(select_tool_callback(p_code))
            red_flow.addWidget(btn)
            self.palette_buttons[p_code] = btn

        for p_code, p_char in black_pieces_conf:
            btn = QPushButton(p_char)
            btn.setFixedSize(32, 32)
            btn.setFont(QFont("SimSun", 12, QFont.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2c3038;
                    color: #ffffff;
                    border: 2px solid #4b505a;
                    border-radius: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #3d424e;
                }
            """)
            btn.clicked.connect(select_tool_callback(p_code))
            black_flow.addWidget(btn)
            self.palette_buttons[p_code] = btn

        # Eraser button
        self.btn_eraser = QPushButton("Tẩy/Xóa")
        self.btn_eraser.setObjectName("btn-secondary")
        self.btn_eraser.setStyleSheet("background-color: #ff5c5c; color: #fffffe; font-size: 11px; border: none; padding: 6px; font-weight: bold; border-radius: 4px;")
        self.btn_eraser.clicked.connect(select_tool_callback("eraser"))
        util_flow.addWidget(self.btn_eraser)

        # Cancel/Normal Move mode button
        self.btn_cancel_pal = QPushButton("Di Chuyển")
        self.btn_cancel_pal.setObjectName("btn-select")
        self.btn_cancel_pal.setStyleSheet("font-size: 11px; border: none; padding: 6px; font-weight: bold; border-radius: 4px;")
        self.btn_cancel_pal.clicked.connect(select_tool_callback(None))
        util_flow.addWidget(self.btn_cancel_pal)

        palette_layout.addLayout(red_flow)
        palette_layout.addLayout(black_flow)
        palette_layout.addLayout(util_flow)
        
        right_layout.addWidget(palette_card)

        # 4. Calibration Slider Card
        cal_card = QFrame()
        cal_card.setObjectName("card")
        cal_layout = QVBoxLayout(cal_card)
        cal_layout.setContentsMargins(12, 12, 12, 12)
        cal_layout.setSpacing(8)

        slider_label_row = QHBoxLayout()
        slider_title = QLabel("Căn lề bàn cờ (Grid Margin)")
        slider_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_margin_value = QLabel(f"{self.config['margin_ratio']*100:.1f}%")
        self.lbl_margin_value.setStyleSheet("color: #7f5af0; font-weight: bold;")
        slider_label_row.addWidget(slider_title)
        slider_label_row.addStretch()
        slider_label_row.addWidget(self.lbl_margin_value)
        cal_layout.addLayout(slider_label_row)

        self.margin_slider = QSlider(Qt.Horizontal)
        self.margin_slider.setMinimum(0)
        self.margin_slider.setMaximum(150)
        self.margin_slider.setValue(int(self.config["margin_ratio"] * 1000))
        self.margin_slider.valueChanged.connect(self.margin_changed)
        cal_layout.addWidget(self.margin_slider)
        
        right_layout.addWidget(cal_card)

        # 5. Turn selection options
        turn_card = QFrame()
        turn_card.setObjectName("card")
        turn_layout = QVBoxLayout(turn_card)
        turn_layout.setContentsMargins(12, 12, 12, 12)
        turn_layout.setSpacing(8)

        turn_title = QLabel("Bên đi nước tiếp theo")
        turn_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        turn_layout.addWidget(turn_title)

        radio_layout = QHBoxLayout()
        self.rad_red = QRadioButton("Đỏ đi (w)")
        self.rad_red.setChecked(True)
        self.rad_black = QRadioButton("Đen đi (b)")
        
        self.turn_group = QButtonGroup()
        self.turn_group.addButton(self.rad_red)
        self.turn_group.addButton(self.rad_black)
        self.turn_group.buttonClicked.connect(self.turn_changed_manually)

        radio_layout.addWidget(self.rad_red)
        radio_layout.addWidget(self.rad_black)
        turn_layout.addLayout(radio_layout)

        # Add visual divider
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #34373c; max-height: 1px;")
        turn_layout.addWidget(sep)

        # Perspective selection
        persp_title = QLabel("Góc nhìn bàn cờ (Quân ở bên dưới)")
        persp_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        turn_layout.addWidget(persp_title)

        persp_layout = QHBoxLayout()
        self.rad_persp_auto = QRadioButton("Tự động (Auto)")
        self.rad_persp_auto.setChecked(True)
        self.rad_persp_red = QRadioButton("Đỏ ở dưới")
        self.rad_persp_black = QRadioButton("Đen ở dưới")
        
        self.persp_group = QButtonGroup()
        self.persp_group.addButton(self.rad_persp_auto)
        self.persp_group.addButton(self.rad_persp_red)
        self.persp_group.addButton(self.rad_persp_black)
        self.persp_group.buttonClicked.connect(self.perspective_changed_manually)

        persp_layout.addWidget(self.rad_persp_auto)
        persp_layout.addWidget(self.rad_persp_red)
        persp_layout.addWidget(self.rad_persp_black)
        turn_layout.addLayout(persp_layout)

        right_layout.addWidget(turn_card)

        # 6. Engine Telemetry Results Display
        telemetry_card = QFrame()
        telemetry_card.setObjectName("card")
        telemetry_layout = QVBoxLayout(telemetry_card)
        telemetry_layout.setContentsMargins(12, 12, 12, 12)
        telemetry_layout.setSpacing(8)

        tele_title = QLabel("Gợi ý Nước Đi từ Pikafish/Fairy")
        tele_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        telemetry_layout.addWidget(tele_title)

        results_grid = QHBoxLayout()
        
        self.val_bestmove = QLabel("Đang chờ...")
        self.val_bestmove.setFont(QFont("Consolas", 14, QFont.Bold))
        self.val_bestmove.setStyleSheet("color: #02c39a;")
        
        self.val_score = QLabel("0.00")
        self.val_score.setFont(QFont("Consolas", 14, QFont.Bold))
        self.val_score.setStyleSheet("color: #7f5af0;")
        
        box_move = QVBoxLayout()
        box_move.addWidget(QLabel("NƯỚC TỐT NHẤT"))
        box_move.addWidget(self.val_bestmove)
        
        box_score = QVBoxLayout()
        box_score.addWidget(QLabel("ĐIỂM ĐÁNH GIÁ"))
        box_score.addWidget(self.val_score)

        results_grid.addLayout(box_move)
        results_grid.addStretch()
        results_grid.addLayout(box_score)
        telemetry_layout.addLayout(results_grid)

        # FEN Text Area
        telemetry_layout.addWidget(QLabel("Trạng thái FEN bàn cờ"))
        self.txt_fen = QTextEdit()
        self.txt_fen.setReadOnly(True)
        self.txt_fen.setFixedHeight(45)
        telemetry_layout.addWidget(self.txt_fen)

        right_layout.addWidget(telemetry_card)
        
        # Add sidebar stretch to top-align all cards
        right_layout.addStretch()
        
        # Add columns to root horizontal layout
        main_layout.addWidget(right_widget, stretch=1)

    def extract_cell_images(self, frame):
        """Helper to crop and resize 90 cells into grayscale images for diffing."""
        if frame is None:
            return None
        h, w, _ = frame.shape
        padding = 40
        margin_ratio = self.config["margin_ratio"]
        
        orig_w = w - 2 * padding
        orig_h = h - 2 * padding
        
        margin_x = int(orig_w * margin_ratio)
        margin_y = int(orig_h * margin_ratio)
        
        playable_w = orig_w - 2 * margin_x
        playable_h = orig_h - 2 * margin_y
        
        col_width = playable_w / 8.0
        row_height = playable_h / 9.0
        cell_size = int(min(col_width, row_height))
        
        cells = {}
        for row in range(10):
            for col in range(9):
                cx = int(padding + margin_x + col * col_width)
                cy = int(padding + margin_y + row * row_height)
                
                x1 = max(0, cx - cell_size // 2)
                y1 = max(0, cy - cell_size // 2)
                x2 = min(w, cx + cell_size // 2)
                y2 = min(h, cy + cell_size // 2)
                
                cropped = frame[y1:y2, x1:x2]
                if cropped.shape[0] != cell_size or cropped.shape[1] != cell_size:
                    cropped = cv2.resize(cropped, (cell_size, cell_size))
                
                # Convert to grayscale for quick comparison
                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                # Resize to a fixed size to ensure absolute size consistency for pixel diffing
                gray = cv2.resize(gray, (50, 50))
                cells[(row, col)] = gray
        return cells

    def reset_reference_cells(self):
        """Captures the current frame and saves the grayscale crops as the new baseline reference."""
        if not self.config["bbox"]:
            return
        padding = 40
        frame = capture_screen_area(self.config["bbox"], padding=padding)
        if frame is not None:
            self.reference_cells = self.extract_cell_images(frame)
            print("[THEO DÕI] Đã thiết lập lại ảnh tham chiếu nền (Reset baseline).")

    def on_palette_selected(self, tool_code):
        """Sets the active piece placement tool and highlights the selected button."""
        # Forward to board widget
        self.board_widget.set_placement_tool(tool_code)
        
        # Clear all highlights
        for p_code, btn in self.palette_buttons.items():
            is_red = p_code.isupper()
            bg = "#c3281e" if is_red else "#2c3038"
            border = "#eb4b41" if is_red else "#4b505a"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: #ffffff;
                    border: 2px solid {border};
                    border-radius: 16px;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    background-color: {"#e03228" if is_red else "#3d424e"};
                }}
            """)
            
        self.btn_eraser.setStyleSheet("background-color: #ff5c5c; color: #fffffe; font-size: 11px; border: none; padding: 6px; font-weight: bold; border-radius: 4px;")
        self.btn_cancel_pal.setStyleSheet("background-color: #02c39a; color: #fffffe; font-size: 11px; border: none; padding: 6px; font-weight: bold; border-radius: 4px;")

        # Apply highlight to selected button
        if tool_code == "eraser":
            self.btn_eraser.setStyleSheet("background-color: #ff3333; color: #fffffe; font-size: 11px; border: 2.5px solid #00e5ff; padding: 6px; font-weight: bold; border-radius: 4px;")
        elif tool_code is None:
            self.btn_cancel_pal.setStyleSheet("background-color: #00ab85; color: #fffffe; font-size: 11px; border: 2.5px solid #00e5ff; padding: 6px; font-weight: bold; border-radius: 4px;")
        else:
            btn = self.palette_buttons.get(tool_code)
            if btn:
                is_red = tool_code.isupper()
                bg = "#c3281e" if is_red else "#2c3038"
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: #ffffff;
                        border: 2.5px solid #00e5ff;
                        border-radius: 16px;
                        padding: 0px;
                    }}
                """)

    def flip_matrix_180(self, matrix):
        """Flips a 10x9 matrix 180 degrees (both vertically and horizontally)."""
        flipped = []
        for row in reversed(matrix):
            flipped.append(list(reversed(row)))
        return flipped

    def flip_uci_move_180(self, move_str):
        """Flips a UCI move string 180 degrees for inverted board perspective."""
        parsed = parse_uci_move(move_str)
        if not parsed:
            return move_str
        c1, r1, c2, r2 = parsed
        # 180 degree flip
        c1_f = 8 - c1
        r1_f = 9 - r1
        c2_f = 8 - c2
        r2_f = 9 - r2
        
        col_chars = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
        return f"{col_chars[c1_f]}{10 - r1_f}{col_chars[c2_f]}{10 - r2_f}"

    def get_active_perspective(self, board_matrix):
        """Determines if the bottom player is Red or Black."""
        if self.rad_persp_red.isChecked():
            return "red"
        elif self.rad_persp_black.isChecked():
            return "black"
        
        # Auto-detect: count red vs black pieces in rows 5-9 (bottom half)
        red_count = 0
        black_count = 0
        for r in range(5, 10):
            for c in range(9):
                piece = board_matrix[r][c]
                if piece != ".":
                    if piece.isupper():
                        red_count += 1
                    else:
                        black_count += 1
        
        return "red" if red_count >= black_count else "black"

    def perspective_changed_manually(self, button):
        self.previous_fen = ""
        self.analyze_current_board()

    def select_board_region(self):
        """Displays the transparent board calibrator overlays."""
        self.overlay.hide()
        self.calibrator = BoardCalibrator()
        self.calibrator.region_selected.connect(self.on_region_selected)
        self.calibrator.show()

    def on_region_selected(self, x, y, w, h):
        """Stores the coordinate bounding box from screen drag selection."""
        self.config["bbox"] = [x, y, w, h]
        self.lbl_geometry.setText(f"Khung toạ độ: {w}x{h} tại ({x}, {y})")
        self.save_config()
        self.overlay.set_region(self.config["bbox"], self.config["margin_ratio"])
        self.show_calibration_grid_briefly()

    def margin_changed(self, value):
        """Updates the margin ratio and displays calibration dots live."""
        self.config["margin_ratio"] = value / 1000.0
        self.lbl_margin_value.setText(f"{self.config['margin_ratio']*100:.1f}%")
        self.save_config()
        if self.config["bbox"]:
            self.overlay.set_region(self.config["bbox"], self.config["margin_ratio"])
            self.show_calibration_grid_briefly()

    def show_calibration_grid_briefly(self):
        """Toggles the visual grid guide and keeps it visible for 2.5s of idle."""
        self.overlay.set_calibration_visible(True)
        self.calibration_grid_timer.start(2500)

    def hide_calibration_grid(self):
        self.overlay.set_calibration_visible(False)

    def turn_changed_manually(self, button):
        """Forces immediate engine re-calculation when active color radio is toggled."""
        self.previous_fen = ""
        self.analyze_current_board()

    def reset_board_matrix(self):
        """Resets the interactive virtual board back to standard starting position."""
        self.board_widget.set_board(STARTING_MATRIX)
        self.previous_fen = ""
        self.rad_red.setChecked(True)
        self.analyze_current_board()

    def clear_board_matrix(self):
        """Clears all pieces from the virtual board matrix."""
        empty_matrix = [["." for _ in range(9)] for _ in range(10)]
        self.board_widget.set_board(empty_matrix)
        self.previous_fen = ""
        self.txt_fen.setText("")
        self.val_bestmove.setText("Bàn cờ trống")
        self.val_bestmove.setStyleSheet("color: #ff5c5c;")
        self.overlay.clear_move()
        self.board_widget.clear_bestmove()

    def on_virtual_board_changed(self, new_matrix):
        """Triggered when the user clicks and moves a piece manually on the virtual board."""
        self.previous_fen = ""
        
        # When a move is completed manually, automatically alternate active color to assist UX
        self.toggle_color_radio()
        
        # If tracking is active, reset baseline reference cells to avoid false difference triggers
        if self.is_tracking:
            self.reset_reference_cells()
            
        self.analyze_current_board()

    def get_active_color_code(self):
        return "w" if self.rad_red.isChecked() else "b"

    def toggle_color_radio(self):
        """Alternates standard turn toggles."""
        if self.rad_red.isChecked():
            self.rad_black.setChecked(True)
        else:
            self.rad_red.setChecked(True)

    def start_coaching(self):
        """Launches background engine and starts continuous loop tracking."""
        if not self.config["bbox"]:
            QMessageBox.warning(self, "Thiếu Cấu Hình", "Vui lòng click 'Chọn Bàn Cờ' trước!")
            return

        try:
            self.status_badge.setText("Khởi động...")
            self.status_badge.setStyleSheet("background-color: #ffc107; border-radius: 12px; font-size: 11px; font-weight: bold; color: #16161a;")
            QApplication.processEvents()
            
            if not self.engine:
                self.engine = PikafishEngine(self.config["engine_path"])
                self.engine.start()
            
        except Exception as e:
            self.status_badge.setText("Lỗi Engine")
            self.status_badge.setStyleSheet("background-color: #ff5c5c; border-radius: 12px; font-size: 11px; font-weight: bold; color: #fffffe;")
            QMessageBox.critical(
                self, 
                "Lỗi Khởi Động Engine", 
                f"Không thể chạy '{self.config['engine_path']}'!\n\nChi tiết lỗi: {e}\n\n"
                "Hãy đặt file engine vào thư mục engine/ và đổi tên/trỏ chuẩn trong config.json."
            )
            return

        # Capture and save baseline reference cells
        padding = 40
        frame = capture_screen_area(self.config["bbox"], padding=padding)
        if frame is None:
            QMessageBox.warning(self, "Lỗi Chụp", "Không thể chụp màn hình bàn cờ để bắt đầu theo dõi!")
            return

        self.reference_cells = self.extract_cell_images(frame)
        self.is_tracking = True
        self.is_scanning = False
        self.previous_fen = ""
        
        self.btn_start.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.status_badge.setText("Đang Theo Dõi")
        self.status_badge.setStyleSheet("background-color: #2cb67d; border-radius: 12px; font-size: 11px; font-weight: bold; color: #fffffe;")
        
        # Start tracking loop at high speed (100ms interval / 10 FPS)
        self.scan_timer.start(100)
        self.resync_timer.start(2000) # Start the 2s autoresync full-scan loop!

    def stop_coaching(self):
        """Stops the tracking loop and terminates background engine process."""
        self.is_tracking = False
        self.is_scanning = False
        self.scan_timer.stop()
        self.resync_timer.stop()
        self.calibration_grid_timer.stop()
        
        if self.engine:
            self.engine.stop()
            self.engine = None
            
        self.overlay.clear_move()
        self.overlay.hide()
        self.board_widget.clear_bestmove()
        
        self.btn_start.setEnabled(True)
        self.btn_select.setEnabled(True)
        self.btn_sync.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        self.status_badge.setText("Chưa kích hoạt")
        self.status_badge.setStyleSheet("background-color: #ff5c5c; border-radius: 12px; font-size: 11px; font-weight: bold; color: #fffffe;")
    def pause_coaching_for_resync(self):
        """Pauses tracking and prompts the user to correct the board manually before resuming."""
        if not self.is_tracking:
            return
        self.is_tracking = False
        self.status_badge.setText("Tạm Dừng Sync")
        self.status_badge.setStyleSheet("background-color: #ff9800; border-radius: 12px; font-size: 11px; font-weight: bold; color: #fffffe;")
        self.btn_start.setEnabled(True)
        self.btn_sync.setEnabled(True)
        self.btn_select.setEnabled(True)
        print("[THEO DÕI] Đã tạm dừng theo dõi để người dùng điều chỉnh thủ công.")

    def sync_board_once(self):
        """Performs a single-shot screen capture to sync the virtual board with the browser."""
        if not self.config["bbox"]:
            QMessageBox.warning(self, "Thiếu Cấu Hình", "Vui lòng click 'Chọn Bàn Cờ' trước!")
            return

        # Start temporary engine for single analysis if not already running
        temp_engine = False
        if not self.engine:
            try:
                self.engine = PikafishEngine(self.config["engine_path"])
                self.engine.start()
                temp_engine = True
            except Exception as e:
                QMessageBox.critical(self, "Lỗi Engine", f"Không thể chạy engine: {e}")
                return

        # Capture and sync board state once
        padding = 40
        frame = capture_screen_area(self.config["bbox"], padding=padding)
        if frame is not None:
            try:
                board_matrix = self.detector.scan_board(frame, self.config["margin_ratio"], padding=padding)
                self.board_widget.set_board(board_matrix)
                pieces_count = sum(1 for row in board_matrix for cell in row if cell != ".")
                print(f"[ĐỒNG BỘ 1L] Đã đồng bộ bàn cờ | Số quân quét được: {pieces_count}/32")
                
                self.previous_fen = ""
                self.analyze_current_board()
            except Exception as e:
                QMessageBox.warning(self, "Lỗi Quét", f"Không thể phân tích bàn cờ: {e}")
        else:
            QMessageBox.warning(self, "Lỗi Chụp", "Không thể chụp hình ảnh màn hình. Hãy kiểm tra lại vùng chọn.")

        # Shut down engine if it was temporary
        if temp_engine and self.engine:
            self.engine.stop()
            self.engine = None

    def process_frame(self):
        """Loop scan capture frame processing (Runs every 100ms for tracking)."""
        if not self.is_tracking or not self.config["bbox"]:
            return

        # 1. Screen Capture via mss with padding buffer
        padding = 40
        frame = capture_screen_area(self.config["bbox"], padding=padding)
        if frame is None:
            return

        # 2. Extract cell grayscale images
        current_cells = self.extract_cell_images(frame)
        if not current_cells or not self.reference_cells:
            return

        # 3. Calculate pixel difference for each cell against baseline
        diffs = []
        for (row, col), current_gray in current_cells.items():
            ref_gray = self.reference_cells.get((row, col))
            if ref_gray is None:
                continue
            
            # Grayscale absolute difference
            diff_img = cv2.absdiff(current_gray, ref_gray)
            mean_diff = np.mean(diff_img)
            diffs.append((mean_diff, row, col))

        # Sort descending to find the top cells with highest difference
        diffs.sort(key=lambda x: x[0], reverse=True)

        if len(diffs) < 3:
            return

        diff_val1, r1, c1 = diffs[0]
        diff_val2, r2, c2 = diffs[1]
        diff_val3, r3, c3 = diffs[2]

        # Standard relative visual diff trigger check (relative gap logic)
        # PlayOK highlighted cells show major change (diff_val > 10.0),
        # while other quiet cells stay under noise floor (diff_val3 < 8.5) and diff_val1 - diff_val3 is large.
        if diff_val1 > 10.0 and diff_val2 > 10.0 and (diff_val1 - diff_val3 > 5.0) and (diff_val2 - diff_val3 > 5.0):
            # Potential move detected between (r1, c1) and (r2, c2)!
            active_color = self.get_active_color_code()
            board_matrix = self.board_widget.get_board()

            # Crop the two cells from the *current* frame to inspect their contents
            h_f, w_f, _ = frame.shape
            orig_w = w_f - 2 * padding
            orig_h = h_f - 2 * padding
            margin_ratio = self.config["margin_ratio"]
            margin_x = int(orig_w * margin_ratio)
            margin_y = int(orig_h * margin_ratio)
            playable_w = orig_w - 2 * margin_x
            playable_h = orig_h - 2 * margin_y
            col_width = playable_w / 8.0
            row_height = playable_h / 9.0
            cell_size = int(min(col_width, row_height))

            # Helper to crop a cell
            def get_cell_crop(r, c):
                cx = int(padding + margin_x + c * col_width)
                cy = int(padding + margin_y + r * row_height)
                x1 = max(0, cx - cell_size // 2)
                y1 = max(0, cy - cell_size // 2)
                x2 = min(w_f, cx + cell_size // 2)
                y2 = min(h_f, cy + cell_size // 2)
                cropped = frame[y1:y2, x1:x2]
                if cropped.shape[0] != cell_size or cropped.shape[1] != cell_size:
                    cropped = cv2.resize(cropped, (cell_size, cell_size))
                return cropped

            crop1 = get_cell_crop(r1, c1)
            crop2 = get_cell_crop(r2, c2)

            # Detect presence and color in the current frame
            is_p1, col1 = self.detector.detect_color_and_presence(crop1)
            is_p2, col2 = self.detector.detect_color_and_presence(crop2)

            src_sq = None
            tgt_sq = None

            # Self-correcting direction detection:
            # The cell that is empty in the current frame is the source square!
            # The cell that contains a piece in the current frame is the target square!
            if not is_p1 and is_p2:
                # Cell 1 is now empty, Cell 2 contains a piece. Move is 1 -> 2
                src_sq = (r1, c1)
                tgt_sq = (r2, c2)
            elif is_p1 and not is_p2:
                # Cell 2 is now empty, Cell 1 contains a piece. Move is 2 -> 1
                src_sq = (r2, c2)
                tgt_sq = (r1, c1)
            else:
                # Fallback: both are empty or both are occupied (very rare, e.g. color detection threshold edge)
                # Fallback to active turn-based color matching
                p1 = board_matrix[r1][c1]
                p2 = board_matrix[r2][c2]
                if active_color == "w":
                    if p1 != "." and p1.isupper() and (p2 == "." or p2.islower()):
                        src_sq = (r1, c1)
                        tgt_sq = (r2, c2)
                    elif p2 != "." and p2.isupper() and (p1 == "." or p1.islower()):
                        src_sq = (r2, c2)
                        tgt_sq = (r1, c1)
                else:
                    if p1 != "." and p1.islower() and (p2 == "." or p2.isupper()):
                        src_sq = (r1, c1)
                        tgt_sq = (r2, c2)
                    elif p2 != "." and p2.islower() and (p1 == "." or p1.isupper()):
                        src_sq = (r2, c2)
                        tgt_sq = (r1, c1)

            if src_sq and tgt_sq:
                # Apply move to Ground Truth board!
                moving_piece = board_matrix[src_sq[0]][src_sq[1]]
                
                # Make sure a piece actually existed on the source square on our virtual board!
                if moving_piece != ".":
                    board_matrix[tgt_sq[0]][tgt_sq[1]] = moving_piece
                    board_matrix[src_sq[0]][src_sq[1]] = "."
                    
                    col_chars = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
                    move_str = f"{col_chars[src_sq[1]]}{10 - src_sq[0]}{col_chars[tgt_sq[1]]}{10 - tgt_sq[0]}"
                    print(f"[THEO DÕI] Đã phát hiện nước đi hợp lệ: {move_str.upper()} ({PIECE_CHAR_MAP.get(moving_piece)} di chuyển)")

                    self.board_widget.set_board(board_matrix)
                    
                    # Update baseline reference cells to the current frame to incorporate highlights
                    self.reference_cells = current_cells
                    
                    # Auto-sync active turn (self-correction): 
                    # If Red piece moved, next turn is Black. If Black piece moved, next turn is Red.
                    if moving_piece.isupper():
                        self.rad_black.setChecked(True)
                    else:
                        self.rad_red.setChecked(True)
                    
                    # Automatically run Pikafish UCI analysis for new state
                    self.analyze_current_board()

    def autoresync_board(self):
        """Periodically scans the actual web board and syncs the virtual board automatically."""
        if not self.is_tracking or not self.config["bbox"]:
            return
            
        padding = 40
        frame = capture_screen_area(self.config["bbox"], padding=padding)
        if frame is None:
            return
            
        try:
            # Perform a full OCR scan of the board
            scanned_matrix = self.detector.scan_board(frame, self.config["margin_ratio"], padding=padding)
            
            # Compare with the virtual board matrix
            current_matrix = self.board_widget.get_board()
            
            different = False
            for r in range(10):
                for c in range(9):
                    if scanned_matrix[r][c] != current_matrix[r][c]:
                        different = True
                        break
                if different:
                    break
                    
            if different:
                print("[AUTOSYNC] Phát hiện sai lệch giữa bàn cờ Web và App! Tự động cập nhật...")
                
                # Try to auto-detect which piece moved to update the turn correctly
                moved_piece = None
                empty_sqs = []
                filled_sqs = []
                for r in range(10):
                    for c in range(9):
                        old_p = current_matrix[r][c]
                        new_p = scanned_matrix[r][c]
                        if old_p != new_p:
                            if old_p != "." and new_p == ".":
                                empty_sqs.append((r, c, old_p))
                            elif old_p == "." and new_p != ".":
                                filled_sqs.append((r, c, new_p))
                            elif old_p != "." and new_p != ".":
                                empty_sqs.append((r, c, old_p))
                                filled_sqs.append((r, c, new_p))
                                
                if len(empty_sqs) == 1 and len(filled_sqs) == 1:
                    moved_piece = empty_sqs[0][2]
                    print(f"[AUTOSYNC] Phát hiện quân {moved_piece} di chuyển từ {empty_sqs[0][:2]} đến {filled_sqs[0][:2]}")
                    if moved_piece.isupper():
                        self.rad_black.setChecked(True)
                    else:
                        self.rad_red.setChecked(True)
                        
                self.board_widget.set_board(scanned_matrix)
                
                # Update baseline reference cells
                self.reference_cells = self.extract_cell_images(frame)
                
                self.previous_fen = ""
                self.analyze_current_board()
                
        except Exception as e:
            print(f"[AUTOSYNC LỖI] Lỗi quét tự động: {e}")

    def analyze_current_board(self):
        """Requests analysis for the active board state on the virtual board."""
        if not self.engine:
            # If not running in continuous mode, we don't start worker unless temp engine is set
            return
            
        board_matrix = self.board_widget.get_board()
        active_color = self.get_active_color_code()
        
        # Detect active perspective (if Black is at bottom, flip matrix for engine)
        perspective = self.get_active_perspective(board_matrix)
        
        # Check if it is the user's turn (user always sits at bottom)
        is_user_turn = (
            (perspective == "red" and active_color == "w") or
            (perspective == "black" and active_color == "b")
        )
        
        if not is_user_turn:
            # It's the opponent's turn! Clear arrow overlays so user is not confused by enemy bestmoves.
            self.val_bestmove.setText("Lượt đối thủ...")
            self.val_bestmove.setStyleSheet("color: #ff9800;")
            self.overlay.clear_move()
            self.board_widget.clear_bestmove()
            self.previous_fen = ""  # Reset FEN cache to analyze immediately when turn switches back
            return
            
        # It is our turn! Run analysis
        if perspective == "black":
            flipped_matrix = self.flip_matrix_180(board_matrix)
            fen = matrix_to_fen(flipped_matrix, active_color)
        else:
            fen = matrix_to_fen(board_matrix, active_color)
        
        if fen != self.previous_fen:
            self.previous_fen = fen
            self.txt_fen.setText(fen)
            
            self.val_bestmove.setText("Đang tính...")
            self.val_bestmove.setStyleSheet("color: #ffc107;")
            
            self.worker = EngineWorker(self.engine, fen, self.config["depth"])
            self.worker.completed.connect(self.on_analysis_completed)
            self.worker.error.connect(self.on_analysis_error)
            self.worker.start()

    def on_analysis_completed(self, result):
        """Handles background calculation output, updates visual labels and transparent arrows."""
        bestmove = result.get("bestmove")
        score = result.get("score", "0.00")
        
        print(f"[ENGINE KẾT QUẢ] Tính xong! Bestmove đề xuất: {bestmove} | Điểm số: {score}")
        
        if bestmove and bestmove != "(none)":
            # Detect active perspective to flip recommendation coordinates if user is Black (bottom)
            board_matrix = self.board_widget.get_board()
            perspective = self.get_active_perspective(board_matrix)
            
            rendered_move = self.flip_uci_move_180(bestmove) if perspective == "black" else bestmove
            
            self.val_bestmove.setText(rendered_move.upper())
            self.val_bestmove.setStyleSheet("color: #02c39a;")
            self.val_score.setText(score)
            
            # Draw recommended arrow on transparent browser overlay
            if self.config["bbox"]:
                self.overlay.set_region(self.config["bbox"], self.config["margin_ratio"])
                self.overlay.set_move(rendered_move)
                
            # Draw recommended arrow on virtual board widget too!
            self.board_widget.set_bestmove(rendered_move)
        else:
            self.val_bestmove.setText("Không có")
            self.val_bestmove.setStyleSheet("color: #ff5c5c;")
            self.overlay.clear_move()
            self.board_widget.clear_bestmove()

    def on_analysis_error(self, err_msg):
        """Logs engine errors."""
        print(f"[ENGINE LỖI] Lỗi phân tích: {err_msg}")
        self.val_bestmove.setText("Lỗi Engine")
        self.val_bestmove.setStyleSheet("color: #ff5c5c;")
        self.overlay.clear_move()
        self.board_widget.clear_bestmove()

    def closeEvent(self, event):
        """Handles clean application cleanup on windows close."""
        self.stop_coaching()
        self.overlay.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = XiangqiCoachApp()
    window.show()
    sys.exit(app.exec_())
