from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
import sys

class BoardCalibrator(QWidget):
    """
    Transparent, borderless full-screen selection widget.
    Allows the user to drag-select the exact coordinate region of the board.
    ESC cancels the selection. Left mouse release confirms selection.
    """
    region_selected = pyqtSignal(int, int, int, int)  # left, top, width, height

    def __init__(self):
        super().__init__()
        # Frameless, stay on top, transparent background
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        
        self.begin = QPoint()
        self.end = QPoint()
        self.is_drawing = False
        
        # Fit to total virtual desktop geometry (supports multi-monitor setups)
        self.setGeometry(QApplication.desktop().geometry())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent dark mask over everything
        painter.fillRect(self.rect(), QColor(10, 10, 15, 140))
        
        if not self.begin.isNull():
            selected_rect = QRect(self.begin, self.end).normalized()
            
            # Punch a hole inside the selection
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selected_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # Draw highly visible neon green border around selection
            border_pen = QPen(QColor(0, 255, 127), 2, Qt.SolidLine)
            painter.setPen(border_pen)
            painter.drawRect(selected_rect)
            
            # Draw selected dimensions and position
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            text = f"Bàn cờ: {selected_rect.width()}x{selected_rect.height()} | Tọa độ: ({selected_rect.x()}, {selected_rect.y()})"
            
            # Render text background box for readability
            text_x = selected_rect.x()
            text_y = max(15, selected_rect.y() - 10)
            painter.drawText(text_x, text_y, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.begin = event.pos()
            self.end = self.begin
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.end = event.pos()
            self.is_drawing = False
            self.update()
            
            # Map local widget coordinates to absolute desktop screen coordinates
            global_begin = self.mapToGlobal(self.begin)
            global_end = self.mapToGlobal(self.end)
            
            rect = QRect(global_begin, global_end).normalized()
            if rect.width() > 30 and rect.height() > 30:
                self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
                self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
