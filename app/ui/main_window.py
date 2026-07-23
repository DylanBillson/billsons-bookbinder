"""Primary application window."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core import SignaturePlanError, SignaturePlanner
from app.models import (
    BlankPages,
    BookProject,
    InputDocument,
)
from app.services import PdfDocumentError, PdfDocumentService
from app.version import APP_DESCRIPTION, APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Main desktop interface for Billson's Bookbinder."""

    def __init__(self, project: BookProject) -> None:
        super().__init__()

        self.project = project

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 750)
        self.resize(1450, 850)

        self._build_menu()
        self._build_interface()
        self._build_status_bar()
        self._refresh_interface()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        add_pdfs_action = file_menu.addAction("&Add PDFs...")
        add_pdfs_action.setShortcut("Ctrl+O")
        add_pdfs_action.triggered.connect(self._select_pdfs)

        add_blanks_action = file_menu.addAction("Add &Blank Pages...")
        add_blanks_action.triggered.connect(self._add_blank_pages)

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
        planning_panel = self._create_planning_panel()

        main_layout.addWidget(controls_panel, stretch=2)
        main_layout.addWidget(planning_panel, stretch=3)

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

        input_group = self._create_input_group()
        signature_group = self._create_signature_group()

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addSpacing(8)
        layout.addWidget(input_group)
        layout.addWidget(signature_group)
        layout.addWidget(self.summary_label)
        layout.addStretch()

        return panel

    def _create_input_group(self) -> QGroupBox:
        group = QGroupBox("Book Input")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel("PDFs and blank-page blocks are combined in the order shown.")
        help_label.setWordWrap(True)

        self.input_list = QListWidget()
        self.input_list.setMinimumHeight(260)
        self.input_list.setAlternatingRowColors(True)
        self.input_list.currentRowChanged.connect(self._update_input_button_states)
        self.input_list.itemDoubleClicked.connect(self._edit_selected_input)

        first_button_row = QHBoxLayout()
        first_button_row.setSpacing(8)

        self.add_pdfs_button = QPushButton("Add PDFs")
        self.add_pdfs_button.clicked.connect(self._select_pdfs)

        self.add_blanks_button = QPushButton("Add Blank Pages")
        self.add_blanks_button.clicked.connect(self._add_blank_pages)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_selected_input)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_selected_input)

        first_button_row.addWidget(self.add_pdfs_button)
        first_button_row.addWidget(self.add_blanks_button)
        first_button_row.addWidget(self.edit_button)
        first_button_row.addWidget(self.remove_button)

        second_button_row = QHBoxLayout()
        second_button_row.setSpacing(8)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self._move_selected_input_up)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self._move_selected_input_down)

        second_button_row.addWidget(self.move_up_button)
        second_button_row.addWidget(self.move_down_button)
        second_button_row.addStretch()

        layout.addWidget(help_label)
        layout.addWidget(self.input_list)
        layout.addLayout(first_button_row)
        layout.addLayout(second_button_row)

        return group

    def _create_signature_group(self) -> QGroupBox:
        group = QGroupBox("Signature Definition")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel(
            "Enter each signature's sheet count in book order. For example: 4-4-4-8-4-4-4"
        )
        help_label.setWordWrap(True)

        self.signature_sequence_edit = QLineEdit()
        self.signature_sequence_edit.setPlaceholderText("Example: 4-4-4-8-4-4-4")
        self.signature_sequence_edit.setClearButtonEnabled(True)
        self.signature_sequence_edit.textChanged.connect(self._signature_sequence_changed)

        separator_help = QLabel("Hyphens, commas and spaces are accepted as separators.")
        separator_help.setWordWrap(True)

        layout.addWidget(help_label)
        layout.addWidget(self.signature_sequence_edit)
        layout.addWidget(separator_help)

        return group

    def _create_planning_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        heading = QLabel("Signature Plan")
        heading_font = heading.font()
        heading_font.setPointSize(14)
        heading_font.setBold(True)
        heading.setFont(heading_font)

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setMinimumHeight(60)
        self.validation_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.plan_summary_label = QLabel()
        self.plan_summary_label.setWordWrap(True)
        self.plan_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.signature_list = QListWidget()
        self.signature_list.setAlternatingRowColors(True)
        self.signature_list.setMinimumSize(550, 450)

        layout.addWidget(heading)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.plan_summary_label)
        layout.addWidget(self.signature_list, stretch=1)

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

        insertion_index = self._next_insertion_index()
        added_count = 0
        duplicate_count = 0
        errors: list[str] = []

        for selected_file in selected_files:
            try:
                document = PdfDocumentService.inspect(Path(selected_file))
            except PdfDocumentError as exc:
                errors.append(str(exc))
                continue

            if self.project.add_document(
                document,
                index=insertion_index,
            ):
                added_count += 1
                insertion_index += 1
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

    def _add_blank_pages(self) -> None:
        quantity, accepted = QInputDialog.getInt(
            self,
            "Add Blank Pages",
            "Number of blank pages:",
            1,
            1,
            9999,
            1,
        )

        if not accepted:
            return

        insertion_index = self._next_insertion_index()

        self.project.add_blank_pages(
            quantity,
            index=insertion_index,
        )

        self._refresh_interface()
        self.input_list.setCurrentRow(insertion_index)
        self.statusBar().showMessage(
            f"Added {quantity} blank {'page' if quantity == 1 else 'pages'}",
            3000,
        )

    def _edit_selected_input(self) -> None:
        selected_index = self.input_list.currentRow()

        if selected_index < 0:
            return

        selected_input = self.project.inputs[selected_index]

        if not isinstance(selected_input, BlankPages):
            return

        quantity, accepted = QInputDialog.getInt(
            self,
            "Edit Blank Pages",
            "Number of blank pages:",
            selected_input.quantity,
            1,
            9999,
            1,
        )

        if not accepted:
            return

        self.project.edit_blank_pages(selected_index, quantity)
        self._refresh_interface()
        self.input_list.setCurrentRow(selected_index)
        self.statusBar().showMessage("Blank pages updated", 3000)

    def _remove_selected_input(self) -> None:
        selected_index = self.input_list.currentRow()

        if selected_index < 0:
            return

        self.project.remove_input(selected_index)
        self._refresh_interface()

        if self.project.inputs:
            next_index = min(
                selected_index,
                len(self.project.inputs) - 1,
            )
            self.input_list.setCurrentRow(next_index)

        self.statusBar().showMessage("Input removed", 3000)

    def _move_selected_input_up(self) -> None:
        selected_index = self.input_list.currentRow()

        if selected_index <= 0:
            return

        self.project.move_input(selected_index, selected_index - 1)
        self._refresh_interface()
        self.input_list.setCurrentRow(selected_index - 1)

    def _move_selected_input_down(self) -> None:
        selected_index = self.input_list.currentRow()

        if selected_index < 0:
            return

        if selected_index >= len(self.project.inputs) - 1:
            return

        self.project.move_input(selected_index, selected_index + 1)
        self._refresh_interface()
        self.input_list.setCurrentRow(selected_index + 1)

    def _signature_sequence_changed(self, value: str) -> None:
        try:
            sheet_counts = SignaturePlanner.parse_signature_sequence(value)
        except SignaturePlanError:
            self.project.signature_sheet_counts = []
        else:
            self.project.signature_sheet_counts = list(sheet_counts)

        self._refresh_summary()
        self._refresh_signature_plan()

    def _refresh_interface(self) -> None:
        self._refresh_input_list()
        self._refresh_summary()
        self._refresh_signature_plan()
        self._update_input_button_states()

    def _refresh_input_list(self) -> None:
        selected_index = self.input_list.currentRow()
        self.input_list.clear()

        for index, item in enumerate(self.project.inputs, start=1):
            if isinstance(item, InputDocument):
                page_word = "page" if item.page_count == 1 else "pages"
                text = f"{index}. {item.filename} — {item.page_count} {page_word}"
            else:
                text = f"{index}. Blank pages × {item.quantity}"

            self.input_list.addItem(text)

        if self.project.inputs and selected_index >= 0:
            self.input_list.setCurrentRow(min(selected_index, len(self.project.inputs) - 1))

    def _refresh_summary(self) -> None:
        pdf_count = len(self.project.documents)
        input_count = len(self.project.inputs)

        self.summary_label.setText(
            f"<b>Current book</b><br>"
            f"Book name: {self.project.name}<br>"
            f"Input entries: {input_count}<br>"
            f"PDF documents: {pdf_count}<br>"
            f"PDF pages: {self.project.source_pdf_page_count}<br>"
            f"Blank pages: {self.project.blank_page_count}<br>"
            f"Total pages: {self.project.total_page_count}<br>"
            f"Defined signatures: {self.project.signature_count}<br>"
            f"Signature capacity: "
            f"{self.project.signature_page_capacity} pages<br>"
            f"Output: {self.project.output_directory}"
        )

    def _refresh_signature_plan(self) -> None:
        self.signature_list.clear()
        sequence_value = self.signature_sequence_edit.text()

        if not self.project.documents:
            self._show_neutral_validation("No PDFs selected. Add at least one PDF to begin.")
            self.plan_summary_label.clear()
            return

        try:
            sheet_counts = SignaturePlanner.parse_signature_sequence(sequence_value)
        except SignaturePlanError as exc:
            self._show_warning_validation(str(exc))
            self.plan_summary_label.setText(f"Current input: {self.project.total_page_count} pages")
            return

        self.project.signature_sheet_counts = list(sheet_counts)

        try:
            plan = SignaturePlanner.create(
                self.project,
                sheet_counts=sheet_counts,
            )
        except SignaturePlanError as exc:
            self._show_warning_validation(str(exc))
            self.plan_summary_label.setText(
                f"Input: {self.project.total_page_count} pages · "
                f"Plan: {sum(sheet_counts)} sheets / "
                f"{sum(sheet_counts) * 4} pages"
            )
            return

        self._show_valid_validation(
            "Signature plan is valid. The plan exactly covers the ordered input pages."
        )

        self.plan_summary_label.setText(
            f"<b>{plan.signature_count} signatures</b> · "
            f"{plan.total_sheet_count} sheets · "
            f"{plan.total_page_count} pages<br>"
            f"PDF pages: {plan.source_pdf_page_count} · "
            f"Blank pages: {plan.blank_page_count}"
        )

        for signature in plan.signatures:
            sheet_word = "sheet" if signature.sheet_count == 1 else "sheets"

            self.signature_list.addItem(
                f"Signature {signature.number} — "
                f"{signature.sheet_count} {sheet_word} / "
                f"{signature.page_count} pages — "
                f"Book pages {signature.start_page_index + 1}"
                f"–{signature.end_page_index + 1}"
            )

    def _show_neutral_validation(self, message: str) -> None:
        self.validation_label.setText(f"<b>{message}</b>")
        self.validation_label.setStyleSheet(
            "QLabel {"
            "background: palette(alternate-base);"
            "border: 1px solid palette(mid);"
            "border-radius: 4px;"
            "padding: 10px;"
            "}"
        )

    def _show_warning_validation(self, message: str) -> None:
        self.validation_label.setText(f"<b>Plan needs attention.</b><br>{message}")
        self.validation_label.setStyleSheet(
            "QLabel {"
            "background: #fff4ce;"
            "color: #5c4400;"
            "border: 1px solid #d6b656;"
            "border-radius: 4px;"
            "padding: 10px;"
            "}"
        )

    def _show_valid_validation(self, message: str) -> None:
        self.validation_label.setText(f"<b>Signature plan is valid.</b><br>{message}")
        self.validation_label.setStyleSheet(
            "QLabel {"
            "background: #e7f4e4;"
            "color: #183b13;"
            "border: 1px solid #71a866;"
            "border-radius: 4px;"
            "padding: 10px;"
            "}"
        )

    def _update_input_button_states(self) -> None:
        selected_index = self.input_list.currentRow()
        has_selection = selected_index >= 0
        final_index = len(self.project.inputs) - 1

        selected_input = self.project.inputs[selected_index] if has_selection else None

        self.edit_button.setEnabled(isinstance(selected_input, BlankPages))
        self.remove_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and selected_index > 0)
        self.move_down_button.setEnabled(has_selection and selected_index < final_index)

    def _next_insertion_index(self) -> int:
        """Return an insertion point immediately after the selection."""

        selected_index = self.input_list.currentRow()

        if selected_index < 0:
            return len(self.project.inputs)

        return selected_index + 1

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
