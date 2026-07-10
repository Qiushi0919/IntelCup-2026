APP_STYLE = """
QWidget {
    color: #dbe8f7;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
QMainWindow, QWidget#root {
    background: #071321;
}
QFrame#header {
    min-height: 52px;
    max-height: 58px;
    background: #0b1b2b;
    border-bottom: 1px solid rgba(76, 111, 143, 0.30);
}
QFrame#card, QFrame#metricBox, QFrame#commandBar {
    background: #0d1d2d;
    border: 1px solid rgba(67, 102, 133, 0.34);
    border-radius: 10px;
}
QFrame#videoCard {
    background: #06111c;
    border: 1px solid rgba(64, 101, 132, 0.24);
    border-radius: 10px;
}
QFrame#compactStatusBar {
    background: #0b1b2b;
    border: 1px solid rgba(67, 102, 133, 0.34);
    border-radius: 8px;
}
QLabel#compactMetrics {
    color: #c4d7e8;
    font-weight: 600;
}
QFrame#candidateIdle, QFrame#candidatePending, QFrame#candidateConfirmed,
QFrame#candidateCancelled {
    background: rgba(8, 24, 38, 0.88);
    border: 1px solid rgba(69, 105, 135, 0.45);
    border-radius: 8px;
}
QFrame#candidatePending {
    background: rgba(69, 46, 12, 0.88);
    border-color: #c08a35;
}
QFrame#candidateConfirmed {
    background: rgba(12, 61, 48, 0.88);
    border-color: #2ebd86;
}
QFrame#candidateCancelled {
    background: rgba(62, 27, 34, 0.88);
    border-color: #a64a56;
}
QLabel#candidateText {
    color: #e6f2fd;
    font-size: 12px;
    font-weight: 700;
}
QFrame#sideNav {
    background: #091827;
    border-right: 1px solid rgba(71, 105, 136, 0.28);
}
QWidget#rightSidebar {
    background: transparent;
}
QLabel#title {
    color: #f3f8fd;
    font-size: 18px;
    font-weight: 700;
}
QLabel#subtitle {
    color: #71879f;
    font-size: 12px;
}
QLabel#sectionTitle {
    color: #edf6ff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#metricValue {
    color: #f4f9ff;
    font-size: 21px;
    font-weight: 700;
}
QLabel#metricName, QLabel#muted {
    color: #71879f;
    font-size: 11px;
}
QLabel#chipGood, QPushButton#statusGood {
    color: #91edc5;
    background: #10382e;
    border: 1px solid rgba(49, 142, 108, 0.55);
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 700;
}
QLabel#chipInfo, QPushButton#statusInfo {
    color: #91d9fb;
    background: #102f46;
    border: 1px solid rgba(48, 116, 155, 0.55);
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 700;
}
QLabel#chipWarn, QPushButton#statusWarn {
    color: #ffd58b;
    background: #392b14;
    border: 1px solid rgba(156, 114, 47, 0.65);
    border-radius: 10px;
    padding: 5px 10px;
    font-weight: 700;
}
QLabel#videoInfoBar {
    min-height: 28px;
    padding: 4px 10px;
    color: #b9d5ea;
    background: #091827;
    border: 1px solid rgba(61, 98, 128, 0.55);
    border-radius: 7px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#miniChipGood, QLabel#miniChipInfo, QLabel#miniChipWarn {
    min-height: 25px;
    padding: 1px 5px;
    border-radius: 7px;
    font-size: 10px;
    font-weight: 700;
}
QLabel#miniChipGood {
    color: #8be9be;
    background: rgba(20, 74, 59, 0.76);
}
QLabel#miniChipInfo {
    color: #8bd5f7;
    background: rgba(20, 61, 88, 0.78);
}
QLabel#miniChipWarn {
    color: #ffd384;
    background: rgba(83, 58, 22, 0.82);
}
QPushButton {
    min-height: 34px;
    padding: 0 13px;
    color: #dceafb;
    background: #132b42;
    border: 1px solid rgba(62, 102, 137, 0.68);
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #1a3a56;
    border-color: #3f7196;
}
QPushButton:pressed {
    background: #0d2032;
}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus,
QCheckBox:focus, QSlider:focus, QTableWidget:focus {
    border: 2px solid #66c2ff;
}
QPushButton#primaryButton {
    color: white;
    background: #1677d8;
    border-color: #2d91e9;
}
QPushButton#dangerButton {
    color: #ffe5e5;
    background: #762d37;
    border-color: #a64a56;
}
QPushButton#warningButton {
    color: #fff0cf;
    background: #644719;
    border-color: #96703a;
}
QPushButton#ghostButton {
    min-height: 26px;
    padding: 0 9px;
    color: #8ca4ba;
    background: transparent;
    border: 1px solid rgba(74, 107, 134, 0.35);
    font-size: 11px;
}
QToolButton#navButton {
    min-height: 42px;
    color: #8ea7bd;
    background: transparent;
    border: 0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    text-align: left;
    padding: 0 12px;
}
QToolButton#navButton:hover {
    color: #eaf6ff;
    background: rgba(29, 72, 106, 0.62);
}
QProgressBar {
    min-height: 15px;
    border: 1px solid rgba(63, 99, 128, 0.65);
    border-radius: 4px;
    background: #14283d;
    text-align: center;
    color: #eaf6ff;
    font-size: 10px;
    font-weight: 700;
}
QProgressBar::chunk {
    border-radius: 4px;
    background: #27c58b;
}
QSplitter::handle {
    background: transparent;
}
QSplitter::handle:hover {
    background: rgba(48, 105, 145, 0.38);
}
QDockWidget {
    color: #dceafb;
    font-weight: 700;
}
QDockWidget::title {
    background: #0c1d30;
    border-bottom: 1px solid #1b334c;
    padding: 9px;
}
QTableWidget, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget {
    color: #cfe0f2;
    background: #091726;
    border: 1px solid rgba(49, 83, 111, 0.55);
    border-radius: 7px;
    gridline-color: #1b3045;
    selection-background-color: #174b73;
}
QHeaderView::section {
    color: #8fa6bd;
    background: #102337;
    border: 0;
    border-bottom: 1px solid #26425c;
    padding: 7px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 32px;
    padding: 0 9px;
    color: #e2edf8;
    background: #0a1929;
    border: 1px solid #244058;
    border-radius: 7px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #2f91da;
}
QComboBox::drop-down {
    width: 30px;
    border-left: 1px solid rgba(68, 105, 135, 0.55);
    background: #102337;
    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}
QComboBox QAbstractItemView {
    color: #e2edf8;
    background: #0a1929;
    border: 1px solid #315a79;
    selection-color: #ffffff;
    selection-background-color: #1677d8;
    outline: 0;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 4px 8px;
    background: #0a1929;
}
QComboBox QAbstractItemView::item:hover {
    color: #ffffff;
    background: #1a4b70;
}
QComboBox QAbstractItemView::item:selected {
    color: #ffffff;
    background: #1677d8;
}
QTabWidget::pane {
    border: 1px solid #1b334c;
    border-radius: 8px;
    background: #0b1b2c;
}
QTabBar::tab {
    padding: 8px 14px;
    color: #7890a8;
    background: #0a1828;
}
QTabBar::tab:selected {
    color: #e8f4ff;
    background: #14334d;
}
QStatusBar {
    min-height: 24px;
    max-height: 26px;
    color: #7590a9;
    background: #071321;
    border-top: 1px solid rgba(54, 84, 109, 0.42);
}
QMenuBar {
    min-height: 24px;
    color: #bcd0e4;
    background: #0a1929;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #174264;
}
QMenu {
    color: #d6e5f4;
    background: #0c1d30;
    border: 1px solid #284259;
}
QToolTip {
    color: #e6f1fc;
    background: #10263b;
    border: 1px solid #386280;
}
QMessageBox {
    background: #f3f7fb;
}
QMessageBox QLabel {
    color: #102033;
    background: transparent;
    font-size: 14px;
    font-weight: 600;
}
QMessageBox QPushButton {
    min-height: 34px;
    padding: 0 14px;
    color: #ffffff;
    background: #123a60;
    border: 1px solid #2f6d9f;
    border-radius: 7px;
    font-weight: 700;
}
QMessageBox QPushButton:hover {
    background: #18517f;
}
QMessageBox QTextEdit {
    color: #102033;
    background: #ffffff;
    border: 1px solid #b8c7d6;
    border-radius: 6px;
}
QScrollBar:vertical {
    width: 8px;
    background: #071321;
}
QScrollBar::handle:vertical {
    min-height: 28px;
    border-radius: 4px;
    background: #24455f;
}
"""


LARGE_DISPLAY_STYLE = """
QWidget {
    font-size: 32px;
}
QFrame#header {
    min-height: 118px;
    max-height: 128px;
}
QLabel#title {
    font-size: 46px;
}
QLabel#subtitle {
    font-size: 28px;
}
QLabel#sectionTitle {
    font-size: 36px;
}
QLabel#metricValue {
    font-size: 54px;
}
QFrame#metricBox {
    min-height: 105px;
}
QLabel#metricName, QLabel#muted {
    font-size: 26px;
}
QLabel#chipGood, QLabel#chipInfo, QLabel#chipWarn,
QPushButton#statusGood, QPushButton#statusInfo, QPushButton#statusWarn {
    padding: 14px 26px;
    border-radius: 18px;
    font-size: 30px;
}
QLabel#miniChipGood, QLabel#miniChipInfo, QLabel#miniChipWarn {
    min-height: 56px;
    padding: 4px 12px;
    font-size: 24px;
}
QPushButton {
    min-height: 76px;
    padding: 0 30px;
    border-radius: 16px;
    font-size: 30px;
}
QPushButton#ghostButton {
    min-height: 60px;
    padding: 0 22px;
    font-size: 26px;
}
QToolButton#navButton {
    min-height: 84px;
    padding: 0 24px;
    font-size: 30px;
}
QProgressBar {
    min-height: 28px;
    font-size: 22px;
}
QLabel#eventTitle {
    font-size: 30px;
}
QLabel#eventDetail {
    font-size: 26px;
}
QDockWidget::title {
    padding: 20px;
    font-size: 30px;
}
QHeaderView::section {
    padding: 18px;
    font-size: 28px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 70px;
    padding: 0 22px;
    font-size: 30px;
}
QComboBox QAbstractItemView {
    color: #e2edf8;
    background: #0a1929;
    border: 2px solid #315a79;
    selection-color: #ffffff;
    selection-background-color: #1677d8;
    font-size: 30px;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    min-height: 58px;
    padding: 8px 18px;
    background: #0a1929;
}
QComboBox QAbstractItemView::item:hover {
    color: #ffffff;
    background: #1a4b70;
}
QComboBox QAbstractItemView::item:selected {
    color: #ffffff;
    background: #1677d8;
}
QToolButton#mapWaypointButton {
    color: #ffffff;
    background: #1677d8;
    border: 2px solid #d7f1ff;
    border-radius: 18px;
    font-size: 20px;
    font-weight: 900;
}
QToolButton#mapWaypointButton:hover {
    background: #25a4ff;
}
QToolButton#mapWaypointButton[routeSelected="true"] {
    color: #071421;
    background: #ffcc4d;
    border-color: #fff0b8;
}
QToolButton#routeTokenButton {
    color: #071421;
    background: #ffcc4d;
    border: 1px solid #ffe7a6;
    border-radius: 13px;
    font-size: 20px;
    font-weight: 900;
    min-width: 36px;
    min-height: 30px;
}
QToolButton#routeTokenButton:hover {
    background: #ffe083;
}
QStatusBar {
    min-height: 52px;
    max-height: 56px;
    font-size: 26px;
}
QMenuBar {
    min-height: 50px;
    font-size: 28px;
}
QScrollBar:vertical {
    width: 18px;
}
"""
