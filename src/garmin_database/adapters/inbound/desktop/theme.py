"""Shared desktop palette and widget style."""

STYLE = """
QWidget { background:#10141c; color:#e9eef5; font-family:'Segoe UI'; font-size:14px; }
QMainWindow { background:#10141c; }
QLabel,QCheckBox { background:transparent; }
QPushButton { background:#252d3a; border:1px solid #303947; border-radius:7px; padding:8px 14px; }
QPushButton:hover { background:#34445a; }
QPushButton:disabled { color:#778393; }
QPushButton[loading=true] { padding-right:34px; }
QPushButton[primary=true] { background:#1678c9; border-color:#268ddf; }
QLineEdit,QDateEdit,QDateTimeEdit,QSpinBox,QComboBox { background:#1c2330; border:1px solid #303947; border-radius:6px; padding:7px; selection-background-color:#164e7c; }
QLineEdit:focus,QDateEdit:focus,QDateTimeEdit:focus,QSpinBox:focus,QComboBox:focus { border-color:#4fa4f3; }
QDateEdit:disabled { color:#778393; }
QCheckBox:disabled { color:#778393; }
QComboBox QAbstractItemView::item:disabled { color:#778393; }
QListWidget,QTextEdit,QTextBrowser,QTableWidget { background:#191e27; border:1px solid #252d3a; border-radius:8px; }
QListWidget#navigation { background:transparent; border:0; outline:0; }
QListWidget#navigation::item { padding:13px 14px; margin:3px 0; border-radius:7px; color:#a3afbf; }
QListWidget#navigation::item:selected { background:#164e7c; color:#e9eef5; }
QListWidget#navigation::item:hover { background:#252d3a; }
QListWidget::item { padding:10px; }
QListWidget::item:selected { background:#164e7c; }
QProgressBar { border:1px solid #303947; border-radius:5px; text-align:center; min-height:22px; }
QProgressBar::chunk { background:#268ddf; }
QToolTip { background:#252d3a; color:white; border:1px solid #4fa4f3; }
QGroupBox { border:0; background:#191e27; border-radius:10px; margin-top:18px; padding:22px 18px 18px; }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 6px; color:#e9eef5; font-weight:600; }
QTabWidget::pane { border:0; padding-top:14px; }
QTabBar::tab { color:#a3afbf; background:transparent; padding:11px 15px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#e9eef5; border-bottom-color:#4fa4f3; }
QHeaderView::section { background:#252d3a; color:#a3afbf; border:0; padding:9px; }
QTableWidget { gridline-color:#252d3a; alternate-background-color:#1c2330; }
QScrollBar:vertical { background:transparent; width:8px; }
QScrollBar::handle:vertical { background:#354154; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
"""
