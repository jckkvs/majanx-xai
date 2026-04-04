import sys
from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent

class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(450, 280)
        self.move(100, 100)
        self._setup_ui()
        self.drag_pos = QPoint()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.bg = QLabel(self)
        self.bg.setStyleSheet("background:rgba(20,24,30,0.85); border-radius:12px; border:1px solid rgba(255,255,255,0.1);")
        self.bg.resize(420, 250)
        
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setStyleSheet("color:#e2e8f0; font-size:14px; padding:10px; line-height:1.6;")
        layout.addWidget(self.text)
        self.text.setText("📷 外部画面待機中...\n画面キャプチャを開始すると自動表示")

    def update_commentary(self, text: str):
        self.text.setText(f"🤖 AI解説 (Dual View)\n\n{text}")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = OverlayWindow()
    win.show()
    sys.exit(app.exec())
