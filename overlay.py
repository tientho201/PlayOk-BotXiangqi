from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPolygon
import math
import re

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

class XiangqiOverlay(QWidget):
    """
    Borderless, transparent, click-through PyQt5 overlay window.
    Positioned exactly over the active chess board area.
    Draws neon highlight circles for move source/target, directional neon arrows, 
    and alignment grid overlays without blocking user interactions or clicks.
    """
    def __init__(self):
        super().__init__()
        # Frame-less, always stays on top, transparent click-through
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.bbox = None
        self.margin_ratio = 0.045
        self.bestmove = None
        self.show_calibration_grid = False

    def set_region(self, bbox, margin_ratio):
        """Updates the physical screen geometry of the overlay window."""
        self.bbox = bbox
        self.margin_ratio = margin_ratio
        if bbox:
            self.setGeometry(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
            self.show()
            self.raise_()
            self.update()
        else:
            self.hide()

    def set_move(self, bestmove):
        """Sets the recommended move to render (e.g. 'h7e7')."""
        self.bestmove = bestmove
        self.raise_()
        self.update()

    def clear_move(self):
        """Clears the rendered move arrows."""
        self.bestmove = None
        self.update()

    def set_calibration_visible(self, visible):
        """Toggles the visibility of the visual alignment grid lines."""
        self.show_calibration_grid = visible
        if visible:
            self.raise_()
        self.update()

    def paintEvent(self, event):
        if not self.bbox:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Margins on both axis
        margin_x = int(w * self.margin_ratio)
        margin_y = int(h * self.margin_ratio)

        # Standard grid sizes
        col_width = (w - 2 * margin_x) / 8.0
        row_height = (h - 2 * margin_y) / 9.0

        # 1. Calibration Assist Grid Mode
        if self.show_calibration_grid:
            # Draw dash cyan lines
            grid_pen = QPen(QColor(0, 191, 255, 130), 1, Qt.DashLine)
            painter.setPen(grid_pen)

            # Draw 9 vertical lines
            for col in range(9):
                x = int(margin_x + col * col_width)
                painter.drawLine(x, margin_y, x, h - margin_y)

            # Draw 10 horizontal lines
            for row in range(10):
                y = int(margin_y + row * row_height)
                painter.drawLine(margin_x, y, w - margin_x, y)

            # Draw small green circles at intersection points
            dot_pen = QPen(QColor(0, 255, 127, 220), 2)
            painter.setPen(dot_pen)
            painter.setBrush(QBrush(QColor(0, 255, 127, 80)))
            for row in range(10):
                for col in range(9):
                    cx = int(margin_x + col * col_width)
                    cy = int(margin_y + row * row_height)
                    painter.drawEllipse(QPoint(cx, cy), 4, 4)

        # 2. Draw Recommended Move Arrow
        if self.bestmove and len(self.bestmove) >= 4:
            parsed = parse_uci_move(self.bestmove)
            if parsed:
                c1, r1, c2, r2 = parsed
                try:
                    # Calculate screen pixel centers
                    x1 = int(margin_x + c1 * col_width)
                    y1 = int(margin_y + r1 * row_height)
                    x2 = int(margin_x + c2 * col_width)
                    y2 = int(margin_y + r2 * row_height)

                    # Set circular size based on board cell spacing
                    r_circ = int(min(col_width, row_height) * 0.35)

                    # Draw Orange/Red source glowing ring
                    start_pen = QPen(QColor(255, 69, 0, 230), 3)
                    painter.setPen(start_pen)
                    painter.setBrush(QBrush(QColor(255, 69, 0, 40)))
                    painter.drawEllipse(QPoint(x1, y1), r_circ, r_circ)

                    # Draw Emerald Green target glowing ring
                    end_pen = QPen(QColor(0, 255, 127, 230), 3)
                    painter.setPen(end_pen)
                    painter.setBrush(QBrush(QColor(0, 255, 127, 40)))
                    painter.drawEllipse(QPoint(x2, y2), r_circ, r_circ)

                    # Draw glowing Cyan arrow connecting the circles
                    arrow_pen = QPen(QColor(0, 238, 255, 230), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                    painter.setPen(arrow_pen)

                    dx = x2 - x1
                    dy = y2 - y1
                    dist = math.hypot(dx, dy)

                    if dist > 0:
                        ux = dx / dist
                        uy = dy / dist

                        # Shorten line coordinates so it starts/ends from rim borders rather than exact centers
                        x1_s = int(x1 + ux * r_circ)
                        y1_s = int(y1 + uy * r_circ)
                        x2_s = int(x2 - ux * r_circ)
                        y2_s = int(y2 - uy * r_circ)

                        painter.drawLine(x1_s, y1_s, x2_s, y2_s)

                        # Paint clean arrow head polygon
                        arrow_len = 15
                        angle = math.atan2(dy, dx)
                        
                        p1_x = x2_s - arrow_len * math.cos(angle - math.pi / 6)
                        p1_y = y2_s - arrow_len * math.sin(angle - math.pi / 6)
                        p2_x = x2_s - arrow_len * math.cos(angle + math.pi / 6)
                        p2_y = y2_s - arrow_len * math.sin(angle + math.pi / 6)

                        arrow_head = QPolygon([
                            QPoint(x2_s, y2_s),
                            QPoint(int(p1_x), int(p1_y)),
                            QPoint(int(p2_x), int(p2_y))
                        ])
                        painter.setBrush(QBrush(QColor(0, 238, 255, 230)))
                        painter.drawPolygon(arrow_head)
                except Exception as e:
                    print(f"Lỗi vẽ overlay: {e}")
