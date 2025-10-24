from __future__ import annotations
import json
from pathlib import Path

LIGHT_QSS = """
QWidget { background: #f7f8fa; color: #222; }
QGroupBox { border: 1px solid #e2e5ea; border-radius: 10px; margin-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; color: #555; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit, QListWidget, QTreeWidget {
  background: #fff; border: 1px solid #d7dbe2; border-radius: 8px;
}
QPushButton { border: 1px solid #cfd6e0; border-radius: 8px; padding: 6px 10px; background: #ffffff; }
QPushButton:hover { background: #eef3ff; }
QToolButton { padding: 4px 8px; }
QTreeWidget::item:selected { background: #e6f0ff; color: #111; }
"""

DARK_QSS = """
QWidget { background: #1f232a; color: #e9edf3; }
QGroupBox { border: 1px solid #3a3f48; border-radius: 10px; margin-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 2px 6px; color: #b7c0cc; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit, QListWidget, QTreeWidget {
  background: #2a2f37; border: 1px solid #3b4250; border-radius: 8px; color: #e9edf3;
}
QPushButton { border: 1px solid #425067; border-radius: 8px; padding: 6px 10px; background: #2d3542; }
QPushButton:hover { background: #38475f; }
QToolButton { padding: 4px 8px; }
QTreeWidget::item:selected { background: #2e5a9f; color: #fff; }
"""

class ThemeManager:
    def __init__(self, data_root: Path):
        self.path = Path(data_root) / "ui_state.json"
        self.state = {"theme": "light"}
        if self.path.exists():
            try:
                self.state.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save(self):
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def apply(self, app):
        theme = self.state.get("theme", "light")
        app.setStyleSheet(LIGHT_QSS if theme == "light" else DARK_QSS)

    def toggle(self, app):
        self.state["theme"] = "dark" if self.state.get("theme") == "light" else "light"
        self.apply(app)
        self.save()
