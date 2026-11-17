"""Sade, modern, Windows 11'e yakın görünüm: Fusion + özel QSS (açık/koyu tema sistemi izler)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from ..paths import data_dir

ACCENT = "#4F6BED"

_LIGHT = {"bg": "#F3F4F8", "card": "#FFFFFF", "text": "#1B1D26", "muted": "#6B7080", "border": "#E1E4EC", "chk_border": "#B8C0D0", "hover": "#E9ECFA", "input": "#FFFFFF"}
_DARK = {"bg": "#16181F", "card": "#1F222C", "text": "#ECEEF6", "muted": "#9AA0B4", "border": "#2E3240", "chk_border": "#454B5E", "hover": "#2A2F44", "input": "#262A36"}

_CHECKMARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="18" height="18">'
    '<path d="M4.2 9.3L7.5 12.6L13.8 5.6" fill="none" stroke="#FFFFFF" '
    'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)


def _ensure_checkmark_svg() -> str:
    """Onay kutuları için yuvarlatılmış beyaz vektörel tik SVG dosyasını hazırlar ve POSIX yolunu döner."""
    candidates = [data_dir() / "checkmark.svg", Path(tempfile.gettempdir()) / "aitranslator_checkmark.svg"]
    for path in candidates:
        try:
            if not path.is_file() or path.read_text(encoding="utf-8") != _CHECKMARK_SVG:
                path.write_text(_CHECKMARK_SVG, encoding="utf-8")
            return path.as_posix()
        except OSError:
            continue
    return candidates[-1].as_posix()


def is_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # eski Qt
        return False


def stylesheet() -> str:
    c = _DARK if is_dark() else _LIGHT
    chk_svg = _ensure_checkmark_svg()
    return f"""
    * {{ font-family: "Segoe UI Variable", "Segoe UI", sans-serif; font-size: 10pt; color: {c['text']}; }}
    QMainWindow, QDialog, #Root {{ background: {c['bg']}; }}
    #LeftPanel {{ background: {c['card']}; border: none; border-right: 1px solid {c['border']}; border-left: 1px solid {c['border']}; }}
    #Sidebar {{ background: transparent; border: none; padding: 10px 6px; outline: 0; }}
    #Sidebar::item {{ padding: 10px 14px; margin: 2px 4px; border-radius: 8px; }}
    #Sidebar::item:hover {{ background: {c['hover']}; }}
    #Sidebar::item:selected {{ background: {ACCENT}; color: white; }}
    #SidebarBottom {{ background: transparent; border-top: 1px solid {c['border']}; padding: 12px 12px 16px 12px; }}
    #Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    #Title {{ font-size: 17pt; font-weight: 600; }}
    #Subtle, QLabel[muted="true"] {{ color: {c['muted']}; }}
    #Warn {{ color: #C77700; }}
    #Ok {{ color: #1E8E5A; }}
    #Err {{ color: #D13438; }}
    QLineEdit, QComboBox, QKeySequenceEdit, QSpinBox, QTableWidget, QPlainTextEdit, QTextEdit {{
        background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 8px; selection-background-color: {ACCENT};
    }}
    QLineEdit:focus, QComboBox:focus, QKeySequenceEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {ACCENT}; }}

    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']}; selection-background-color: {ACCENT}; selection-color: white; }}
    QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 16px; }}
    QPushButton:hover {{ background: {c['hover']}; }}
    QPushButton#Primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: #6479F0; }}
    QCheckBox {{ spacing: 10px; padding: 4px 0; }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1.5px solid {c['chk_border']};
        background: {c['input']};
    }}
    QCheckBox::indicator:unchecked:hover {{
        border: 1.5px solid {ACCENT};
        background: {c['hover']};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border: 1.5px solid {ACCENT};
        image: url("{chk_svg}");
    }}
    QCheckBox::indicator:checked:hover {{
        background: #3E58D8;
        border: 1.5px solid #3E58D8;
        image: url("{chk_svg}");
    }}
    QCheckBox::indicator:checked:disabled {{
        background: #9AA8EE;
        border: 1.5px solid #9AA8EE;
        image: url("{chk_svg}");
    }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::scroller {{ width: 0px; }}
    QTabBar QToolButton {{ width: 0px; height: 0px; border: none; background: transparent; }}
    QTabBar::tab {{
        padding: 8px 13px;
        margin-right: 6px;
        border-radius: 8px;
        border: 1px solid {c['border']};
        background: {c['card']};
        color: {c['muted']};
        font-size: 10pt;
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        background: {c['hover']};
        color: {c['text']};
        border: 1px solid {c['chk_border']};
    }}
    QTabBar::tab:selected {{
        background: {ACCENT};
        color: white;
        border: 1px solid {ACCENT};
        font-weight: 600;
    }}
    QHeaderView::section {{ background: {c['card']}; border: none; border-bottom: 1px solid {c['border']}; padding: 6px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 0; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; height: 0px; }}
    QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px; }}
    QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {ACCENT}; color: white; }}
    """


def make_app_icon(size: int = 256) -> QIcon:
    """Uygulama simgesi kod ile çizilir (ikili varlık dosyası gerekmez)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#6A82FB"))
    grad.setColorAt(1, QColor("#3A4FD4"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88), size * 0.22, size * 0.22)
    p.fillPath(path, grad)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", int(size * 0.30), QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, size * 0.10, size, size * 0.55), Qt.AlignmentFlag.AlignCenter, "A文")
    pen = QPen(QColor("white"), size * 0.035, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    y = size * 0.76
    p.drawLine(int(size * 0.28), int(y), int(size * 0.72), int(y))
    p.drawLine(int(size * 0.62), int(y - size * 0.06), int(size * 0.72), int(y))
    p.drawLine(int(size * 0.62), int(y + size * 0.06), int(size * 0.72), int(y))
    p.end()
    return QIcon(pm)


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
