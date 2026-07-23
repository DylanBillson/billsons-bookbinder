"""Primary application window."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.models import BookProject
from app.services import PdfDocumentError, PdfDocumentService
from app.version import APP_DESCRIPTION, APP_NAME, APP_VERSION


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
        self._refresh_interface()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        add_pdfs_action = file_menu.addAction("&Add PDFs...")
        add_pdfs_action.setShortcut("Ctrl+O")
        add_pdfs_action.triggered.connect(self._select_pdfs)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        help_menu = self.menuBar().addMenu("&Help")

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

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

        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)

        input_heading = QLabel("Input PDFs")
        input_font = input_heading.font()
        input_font.setPointSize(12)
        input_font.setBold(True)
        input_heading.setFont(input_font)

        self.document_list = QListWidget()
        self.document_list.setMinimumHeight(260)
        self.document_list.setAlternatingRowColors(True)
        self.document_list.currentRowChanged.connect(self._update_document_button_states)

        document_buttons = QHBoxLayout()
        document_buttons.setSpacing(8)

        self.add_button = QPushButton("Add PDFs")
        self.add_button.clicked.connect(self._select_pdfs)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_selected_document)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self._move_selected_document_up)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self._move_selected_document_down)

        document_buttons.addWidget(self.add_button)
        document_buttons.addWidget(self.remove_button)
        document_buttons.addWidget(self.move_up_button)
        document_buttons.addWidget(self.move_down_button)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addSpacing(8)
        layout.addWidget(input_heading)
        layout.addWidget(self.document_list)
        layout.addLayout(document_buttons)
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

        self.preview_placeholder = QLabel("Add one or more PDFs to begin preparing the book.")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setWordWrap(True)
        self.preview_placeholder.setMinimumSize(500, 500)
        self.preview_placeholder.setStyleSheet(
            "QLabel {border: 1px solid palette(mid);border-radius: 4px;padding: 20px;}"
        )

        layout.addWidget(heading)
        layout.addWidget(self.preview_placeholder, stretch=1)

        return panel

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.showMessage("Ready")

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setContentsMargins(8, 0, 8, 0)
        status_bar.addPermanentWidget(version_label)

        self.setStatusBar(status_bar)

    def _select_pdfs(self) -> None:
        selected_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF documents",
            str(Path.home()),
            "PDF documents (*.pdf)",
        )

        if not selected_files:
            return

        added_count = 0
        duplicate_count = 0
        errors: list[str] = []

        for selected_file in selected_files:
            try:
                document = PdfDocumentService.inspect(Path(selected_file))
            except PdfDocumentError as exc:
                errors.append(str(exc))
                continue

            if self.project.add_document(document):
                added_count += 1
            else:
                duplicate_count += 1

        self._refresh_interface()

        status_parts: list[str] = []

        if added_count:
            status_parts.append(f"Added {added_count} PDF{'' if added_count == 1 else 's'}")

        if duplicate_count:
            status_parts.append(
                f"ignored {duplicate_count} duplicate{'' if duplicate_count == 1 else 's'}"
            )

        if status_parts:
            self.statusBar().showMessage(", ".join(status_parts), 5000)

        if errors:
            QMessageBox.warning(
                self,
                "Some PDFs could not be added",
                "\n\n".join(errors),
            )

    def _remove_selected_document(self) -> None:
        selected_index = self.document_list.currentRow()

        if selected_index < 0:
            return

        self.project.remove_document(selected_index)
        self._refresh_interface()

        if self.project.documents:
            next_index = min(selected_index, len(self.project.documents) - 1)
            self.document_list.setCurrentRow(next_index)

        self.statusBar().showMessage("PDF removed", 3000)

    def _move_selected_document_up(self) -> None:
        selected_index = self.document_list.currentRow()

        if selected_index <= 0:
            return

        self.project.move_document(selected_index, selected_index - 1)
        self._refresh_interface()
        self.document_list.setCurrentRow(selected_index - 1)

    def _move_selected_document_down(self) -> None:
        selected_index = self.document_list.currentRow()

        if selected_index < 0:
            return

        if selected_index >= len(self.project.documents) - 1:
            return

        self.project.move_document(selected_index, selected_index + 1)
        self._refresh_interface()
        self.document_list.setCurrentRow(selected_index + 1)

    def _refresh_interface(self) -> None:
        self._refresh_document_list()
        self._refresh_summary()
        self._refresh_preview_placeholder()
        self._update_document_button_states()

    def _refresh_document_list(self) -> None:
        selected_index = self.document_list.currentRow()

        self.document_list.clear()

        for index, document in enumerate(self.project.documents, start=1):
            page_word = "page" if document.page_count == 1 else "pages"
            self.document_list.addItem(
                f"{index}. {document.filename} — {document.page_count} {page_word}"
            )

        if self.project.documents and selected_index >= 0:
            self.document_list.setCurrentRow(min(selected_index, len(self.project.documents) - 1))

    def _refresh_summary(self) -> None:
        document_count = len(self.project.documents)
        document_word = "document" if document_count == 1 else "documents"
        page_word = "page" if self.project.source_page_count == 1 else "pages"

        self.summary_label.setText(
            f"<b>Current project</b><br>"
            f"Book name: {self.project.name}<br>"
            f"Input: {document_count} {document_word}<br>"
            f"Source pages: {self.project.source_page_count} {page_word}<br>"
            f"Sheets per signature: "
            f"{self.project.print_settings.sheets_per_signature}<br>"
            f"Pages per signature: {self.project.pages_per_signature}<br>"
            f"Output: {self.project.output_directory}"
        )

    def _refresh_preview_placeholder(self) -> None:
        if not self.project.documents:
            self.preview_placeholder.setText("Add one or more PDFs to begin preparing the book.")
            return

        self.preview_placeholder.setText(
            f"{len(self.project.documents)} PDF document"
            f"{'' if len(self.project.documents) == 1 else 's'} selected\n\n"
            f"{self.project.source_page_count} source pages\n\n"
            "Signature planning and live preview will be added next."
        )

    def _update_document_button_states(self) -> None:
        selected_index = self.document_list.currentRow()
        has_selection = selected_index >= 0
        final_index = len(self.project.documents) - 1

        self.remove_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and selected_index > 0)
        self.move_down_button.setEnabled(has_selection and selected_index < final_index)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            (
                f"<h2>{APP_NAME}</h2>"
                f"<p>{APP_DESCRIPTION}</p>"
                f"<p>Version {APP_VERSION}</p>"
                f"<p>Part of the Billson Stack.</p>"
            ),
        )
