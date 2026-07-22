"""Primary application window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.models import BookProject
from app.version import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Main desktop interface for Billson's Bookbinder."""

    def __init__(self, project: BookProject) -> None:
        super().__init__()

        self.project = project

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1050, 700)
        self.resize(1280, 800)

        self._build_menu()
        self._build_interface()
        self._build_status_bar()
        self._refresh_summary()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        help_menu = self.menuBar().addMenu("&Help")

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about_placeholder)

    def _build_interface(self) -> None:
        central_widget = QWidget(self)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        controls_panel = self._create_controls_panel()
        preview_panel = self._create_preview_panel()

        main_layout.addWidget(controls_panel, stretch=2)
        main_layout.addWidget(preview_panel, stretch=3)

        self.setCentralWidget(central_widget)

    def _create_controls_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        heading = QLabel(APP_NAME)
        heading_font = heading.font()
        heading_font.setPointSize(20)
        heading_font.setBold(True)
        heading.setFont(heading_font)

        input_heading = QLabel("Input PDFs")
        input_font = input_heading.font()
        input_font.setPointSize(12)
        input_font.setBold(True)
        input_heading.setFont(input_font)

        input_placeholder = QLabel(
            "No PDF documents selected.\n\n"
            "PDF ordering controls will be added next."
        )
        input_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_placeholder.setMinimumHeight(220)
        input_placeholder.setStyleSheet(
            "QLabel {"
            "border: 1px solid palette(mid);"
            "border-radius: 4px;"
            "padding: 20px;"
            "}"
        )

        add_button = QPushButton("Add PDFs")
        add_button.setEnabled(False)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addWidget(input_heading)
        layout.addWidget(input_placeholder)
        layout.addWidget(add_button)
        layout.addSpacing(12)
        layout.addWidget(self.summary_label)
        layout.addStretch()

        return panel

    def _create_preview_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Preview")
        heading_font = heading.font()
        heading_font.setPointSize(12)
        heading_font.setBold(True)
        heading.setFont(heading_font)

        preview_placeholder = QLabel(
            "The imposed sheet preview will appear here."
        )
        preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_placeholder.setMinimumSize(500, 500)
        preview_placeholder.setStyleSheet(
            "QLabel {"
            "border: 1px solid palette(mid);"
            "border-radius: 4px;"
            "padding: 20px;"
            "}"
        )

        layout.addWidget(heading)
        layout.addWidget(preview_placeholder, stretch=1)

        return panel

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.showMessage("Ready")

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setContentsMargins(8, 0, 8, 0)
        status_bar.addPermanentWidget(version_label)

        self.setStatusBar(status_bar)

    def _refresh_summary(self) -> None:
        self.summary_label.setText(
            f"<b>Current project</b><br>"
            f"Book name: {self.project.name}<br>"
            f"Source pages: {self.project.source_page_count}<br>"
            f"Sheets per signature: "
            f"{self.project.print_settings.sheets_per_signature}<br>"
            f"Pages per signature: {self.project.pages_per_signature}"
        )

    def _show_about_placeholder(self) -> None:
        self.statusBar().showMessage(
            f"{APP_NAME} version {APP_VERSION}",
            5000,
        )