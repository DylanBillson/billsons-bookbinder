"""Primary application window."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core import (
    BookletImposer,
    BookletImpositionError,
    LogicalPageStreamBuilder,
    LogicalPageStreamError,
    SignaturePlanError,
    SignaturePlanner,
)
from app.models import (
    BlankPages,
    BookImposition,
    BookProject,
    ImposedSignature,
    InputDocument,
    PageFittingMode,
    PaperSize,
)
from app.services import (
    PdfDocumentError,
    PdfDocumentService,
    SignaturePdfExporter,
    SignaturePdfExportError,
)
from app.version import APP_DESCRIPTION, APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    """Main desktop interface for Billson's Bookbinder."""

    PLANNING_PAGE_INDEX = 0
    OUTPUT_PAGE_INDEX = 1

    def __init__(self, project: BookProject) -> None:
        super().__init__()

        self.project = project
        self.current_imposition: BookImposition | None = None
        self.last_export_directory: Path | None = None
        self.separate_duplex_outputs = False

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1280, 760)
        self.resize(1680, 960)

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
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._create_planning_page())
        self.page_stack.addWidget(self._create_output_page())

        central_layout.addWidget(self.page_stack)
        self.setCentralWidget(central_widget)

    def _create_planning_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            self._create_page_header(
                title=APP_NAME,
                subtitle=(
                    "Build the ordered book, define its signatures, "
                    "and verify the booklet imposition."
                ),
            )
        )

        page_splitter = QSplitter(Qt.Orientation.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        input_column = self._create_input_column()
        definition_column = self._create_definition_column()
        planning_column = self._create_imposition_column()

        page_splitter.addWidget(input_column)
        page_splitter.addWidget(definition_column)
        page_splitter.addWidget(planning_column)

        page_splitter.setStretchFactor(0, 4)
        page_splitter.setStretchFactor(1, 3)
        page_splitter.setStretchFactor(2, 5)
        page_splitter.setSizes([500, 390, 650])

        navigation_row = QHBoxLayout()
        navigation_row.setSpacing(10)

        navigation_help = QLabel("Continue when the signature plan exactly matches the book.")
        navigation_help.setWordWrap(True)

        self.next_button = QPushButton("Next: Print Setup and Export →")
        self.next_button.setMinimumHeight(42)
        self.next_button.setMinimumWidth(260)
        self.next_button.clicked.connect(self._show_output_page)

        navigation_row.addWidget(navigation_help)
        navigation_row.addStretch()
        navigation_row.addWidget(self.next_button)

        layout.addWidget(page_splitter, stretch=1)
        layout.addLayout(navigation_row)

        return page

    def _create_output_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        self.back_button = QPushButton("← Back to Book Setup")
        self.back_button.setMinimumHeight(40)
        self.back_button.setMinimumWidth(210)
        self.back_button.clicked.connect(self._show_planning_page)

        title_container = self._create_page_header(
            title="Print Setup and Export",
            subtitle=(
                "Configure page placement and printing, preview the "
                "imposed output, then generate the signature PDFs."
            ),
        )

        header_layout.addWidget(self.back_button)
        header_layout.addWidget(title_container, stretch=1)

        page_splitter = QSplitter(Qt.Orientation.Horizontal)
        page_splitter.setChildrenCollapsible(False)

        settings_column = self._create_output_settings_column()
        preview_column = self._create_pdf_preview_column()

        page_splitter.addWidget(settings_column)
        page_splitter.addWidget(preview_column)

        page_splitter.setStretchFactor(0, 2)
        page_splitter.setStretchFactor(1, 5)
        page_splitter.setSizes([430, 1050])

        layout.addWidget(header)
        layout.addWidget(page_splitter, stretch=1)

        return page

    def _create_page_header(
        self,
        *,
        title: str,
        subtitle: str,
    ) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        heading = QLabel(title)
        heading_font = heading.font()
        heading_font.setPointSize(20)
        heading_font.setBold(True)
        heading.setFont(heading_font)

        description = QLabel(subtitle)
        description.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)

        return container

    def _create_input_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        input_group = self._create_input_group()
        input_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout.addWidget(input_group, stretch=1)

        return column

    def _create_definition_column(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_signature_group())
        layout.addWidget(self._create_duplex_group())
        layout.addWidget(self._create_book_summary_group())
        layout.addStretch()

        return self._wrap_in_scroll_area(content)

    def _create_imposition_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QLabel("Signature Plan and Imposition Preview")
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

        preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_splitter.setChildrenCollapsible(False)

        signature_group = self._create_signature_list_group()
        sheet_preview_group = self._create_sheet_preview_group()

        preview_splitter.addWidget(signature_group)
        preview_splitter.addWidget(sheet_preview_group)

        preview_splitter.setStretchFactor(0, 4)
        preview_splitter.setStretchFactor(1, 1)
        preview_splitter.setSizes([620, 170])

        layout.addWidget(heading)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.plan_summary_label)
        layout.addWidget(preview_splitter, stretch=1)

        return column

    def _create_output_settings_column(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_margin_group())
        layout.addWidget(self._create_print_options_group())
        layout.addWidget(self._create_export_group())
        layout.addStretch()

        return self._wrap_in_scroll_area(content)

    def _create_pdf_preview_column(self) -> QWidget:
        group = QGroupBox("PDF Preview")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.pdf_preview_summary_label = QLabel(
            "A valid signature plan is required before previewing output."
        )
        self.pdf_preview_summary_label.setWordWrap(True)
        self.pdf_preview_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_layout.setSpacing(14)

        self.pdf_preview_placeholder = QLabel(
            "<h2>Imposed PDF Preview</h2>"
            "<p>The rendered page preview will appear here.</p>"
            "<p>This section will show each generated sheet side using "
            "the selected paper size, margins, fitting mode and duplex "
            "settings.</p>"
        )
        self.pdf_preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_preview_placeholder.setWordWrap(True)
        self.pdf_preview_placeholder.setMinimumSize(700, 500)
        self.pdf_preview_placeholder.setStyleSheet(
            "QLabel {"
            "background: palette(base);"
            "border: 1px solid palette(mid);"
            "border-radius: 6px;"
            "padding: 30px;"
            "}"
        )

        preview_layout.addStretch()
        preview_layout.addWidget(self.pdf_preview_placeholder)
        preview_layout.addStretch()

        preview_scroll.setWidget(preview_container)

        layout.addWidget(self.pdf_preview_summary_label)
        layout.addWidget(preview_scroll, stretch=1)

        return group

    def _wrap_in_scroll_area(self, widget: QWidget) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(widget)

        return scroll_area

    def _create_input_group(self) -> QGroupBox:
        group = QGroupBox("Book Input")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel("PDFs and blank-page blocks are combined in the order shown.")
        help_label.setWordWrap(True)

        self.input_list = QListWidget()
        self.input_list.setAlternatingRowColors(True)
        self.input_list.setMinimumHeight(440)
        self.input_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.input_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.input_list.currentRowChanged.connect(self._update_input_button_states)
        self.input_list.itemDoubleClicked.connect(self._edit_selected_input)

        first_button_row = QHBoxLayout()
        first_button_row.setSpacing(8)

        self.add_pdfs_button = QPushButton("Add PDFs")
        self.add_pdfs_button.clicked.connect(self._select_pdfs)

        self.add_blanks_button = QPushButton("Add Blank Pages")
        self.add_blanks_button.clicked.connect(self._add_blank_pages)

        first_button_row.addWidget(self.add_pdfs_button)
        first_button_row.addWidget(self.add_blanks_button)

        second_button_row = QHBoxLayout()
        second_button_row.setSpacing(8)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_selected_input)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._remove_selected_input)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self._move_selected_input_up)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self._move_selected_input_down)

        second_button_row.addWidget(self.edit_button)
        second_button_row.addWidget(self.remove_button)
        second_button_row.addWidget(self.move_up_button)
        second_button_row.addWidget(self.move_down_button)

        layout.addWidget(help_label)
        layout.addWidget(self.input_list, stretch=1)
        layout.addLayout(first_button_row)
        layout.addLayout(second_button_row)

        return group

    def _create_signature_group(self) -> QGroupBox:
        group = QGroupBox("Signature Definition")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel("Enter each signature's sheet count in book order.")
        help_label.setWordWrap(True)

        example_label = QLabel("Example: 4-4-4-8-4-4-4")
        example_label.setWordWrap(True)

        self.signature_sequence_edit = QLineEdit()
        self.signature_sequence_edit.setPlaceholderText("Example: 4-4-4-8-4-4-4")
        self.signature_sequence_edit.setClearButtonEnabled(True)
        self.signature_sequence_edit.textChanged.connect(self._signature_sequence_changed)

        separator_help = QLabel("Hyphens, commas and spaces are accepted as separators.")
        separator_help.setWordWrap(True)

        layout.addWidget(help_label)
        layout.addWidget(example_label)
        layout.addWidget(self.signature_sequence_edit)
        layout.addWidget(separator_help)

        return group

    def _create_duplex_group(self) -> QGroupBox:
        group = QGroupBox("Duplex Output")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.separate_duplex_checkbox = QCheckBox(
            "Create separate A-side and B-side signature PDFs"
        )
        self.separate_duplex_checkbox.setChecked(self.separate_duplex_outputs)
        self.separate_duplex_checkbox.stateChanged.connect(self._duplex_output_changed)

        help_label = QLabel(
            "When enabled, front and back sheet sides will eventually "
            "be exported separately for printers or workflows that "
            "cannot use ordinary duplex output."
        )
        help_label.setWordWrap(True)

        status_label = QLabel(
            "The interface option is ready. Separate-file export will "
            "be connected in the next implementation stage."
        )
        status_label.setWordWrap(True)
        status_label.setStyleSheet(
            "QLabel {"
            "background: palette(alternate-base);"
            "border: 1px solid palette(mid);"
            "border-radius: 4px;"
            "padding: 8px;"
            "}"
        )

        layout.addWidget(self.separate_duplex_checkbox)
        layout.addWidget(help_label)
        layout.addWidget(status_label)

        return group

    def _create_book_summary_group(self) -> QGroupBox:
        group = QGroupBox("Current Book")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        summary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        summary_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        summary_scroll.setMinimumHeight(260)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary_label.setContentsMargins(4, 4, 4, 4)

        summary_scroll.setWidget(self.summary_label)

        layout.addWidget(summary_scroll)

        return group

    def _create_signature_list_group(self) -> QGroupBox:
        group = QGroupBox("Signatures")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel("Select a signature to inspect its physical sheets.")
        help_label.setWordWrap(True)

        self.signature_list = QListWidget()
        self.signature_list.setAlternatingRowColors(True)
        self.signature_list.setMinimumWidth(400)
        self.signature_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.signature_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.signature_list.currentRowChanged.connect(self._selected_signature_changed)

        layout.addWidget(help_label)
        layout.addWidget(self.signature_list, stretch=1)

        return group

    def _create_sheet_preview_group(self) -> QGroupBox:
        group = QGroupBox("Selected")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.selected_signature_summary_label = QLabel("Select a valid signature.")
        self.selected_signature_summary_label.setWordWrap(True)
        self.selected_signature_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.sheet_preview_list = QListWidget()
        self.sheet_preview_list.setAlternatingRowColors(True)
        self.sheet_preview_list.setMinimumWidth(140)
        self.sheet_preview_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sheet_preview_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        layout.addWidget(self.selected_signature_summary_label)
        layout.addWidget(self.sheet_preview_list, stretch=1)

        return group

    def _create_margin_group(self) -> QGroupBox:
        group = QGroupBox("Margins")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        help_label = QLabel("Margins are measured in millimetres on each imposed half-sheet.")
        help_label.setWordWrap(True)

        self.binding_margin_spin = self._create_margin_spinbox()
        self.outer_margin_spin = self._create_margin_spinbox()
        self.top_margin_spin = self._create_margin_spinbox()
        self.bottom_margin_spin = self._create_margin_spinbox()

        self.binding_margin_spin.setValue(self.project.print_settings.margins.binding_mm)
        self.outer_margin_spin.setValue(self.project.print_settings.margins.outer_mm)
        self.top_margin_spin.setValue(self.project.print_settings.margins.top_mm)
        self.bottom_margin_spin.setValue(self.project.print_settings.margins.bottom_mm)

        self.binding_margin_spin.valueChanged.connect(self._print_settings_changed)
        self.outer_margin_spin.valueChanged.connect(self._print_settings_changed)
        self.top_margin_spin.valueChanged.connect(self._print_settings_changed)
        self.bottom_margin_spin.valueChanged.connect(self._print_settings_changed)

        layout.addWidget(help_label)
        layout.addLayout(
            self._create_labelled_control_row(
                "Binding / inner",
                self.binding_margin_spin,
            )
        )
        layout.addLayout(
            self._create_labelled_control_row(
                "Outer",
                self.outer_margin_spin,
            )
        )
        layout.addLayout(
            self._create_labelled_control_row(
                "Top",
                self.top_margin_spin,
            )
        )
        layout.addLayout(
            self._create_labelled_control_row(
                "Bottom",
                self.bottom_margin_spin,
            )
        )

        return group

    def _create_margin_spinbox(self) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.0, 100.0)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(0.5)
        spinbox.setSuffix(" mm")
        spinbox.setMinimumWidth(120)

        return spinbox

    def _create_labelled_control_row(
        self,
        label_text: str,
        control: QWidget,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setWordWrap(True)

        row.addWidget(label, stretch=1)
        row.addWidget(control)

        return row

    def _create_print_options_group(self) -> QGroupBox:
        group = QGroupBox("Print Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.paper_size_combo = QComboBox()

        for paper_size in PaperSize:
            self.paper_size_combo.addItem(
                self._enum_display_name(paper_size),
                paper_size,
            )

        self._select_combo_data(
            self.paper_size_combo,
            self.project.print_settings.paper_size,
        )
        self.paper_size_combo.currentIndexChanged.connect(self._print_settings_changed)

        self.fitting_mode_combo = QComboBox()

        for fitting_mode in PageFittingMode:
            self.fitting_mode_combo.addItem(
                self._enum_display_name(fitting_mode),
                fitting_mode,
            )

        self._select_combo_data(
            self.fitting_mode_combo,
            self.project.print_settings.fitting_mode,
        )
        self.fitting_mode_combo.currentIndexChanged.connect(self._print_settings_changed)

        orientation_value = QLabel("Landscape imposed sheets")
        orientation_value.setWordWrap(True)

        print_help = QLabel(
            "Generated files should be printed at 100% scale. For "
            "ordinary duplex output, flip on the short edge and do not "
            "enable the printer's own booklet mode."
        )
        print_help.setWordWrap(True)

        layout.addLayout(
            self._create_labelled_control_row(
                "Paper size",
                self.paper_size_combo,
            )
        )
        layout.addLayout(
            self._create_labelled_control_row(
                "Page fitting",
                self.fitting_mode_combo,
            )
        )
        layout.addLayout(
            self._create_labelled_control_row(
                "Orientation",
                orientation_value,
            )
        )
        layout.addWidget(print_help)

        return group

    def _create_export_group(self) -> QGroupBox:
        group = QGroupBox("PDF Export")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        help_label = QLabel("Generate one imposed PDF per signature.")
        help_label.setWordWrap(True)

        self.output_directory_label = QLabel()
        self.output_directory_label.setWordWrap(True)
        self.output_directory_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.choose_output_button = QPushButton("Choose Output Folder")
        self.choose_output_button.clicked.connect(self._choose_output_directory)

        self.export_button = QPushButton("Export Signatures")
        self.export_button.setMinimumHeight(42)
        self.export_button.clicked.connect(self._export_signatures)

        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.clicked.connect(self._open_output_directory)
        self.open_output_button.setEnabled(False)

        layout.addWidget(help_label)
        layout.addWidget(self.output_directory_label)
        layout.addWidget(self.choose_output_button)
        layout.addWidget(self.export_button)
        layout.addWidget(self.open_output_button)

        return group

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.showMessage("Ready")

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setContentsMargins(8, 0, 8, 0)
        status_bar.addPermanentWidget(version_label)

        self.setStatusBar(status_bar)

    def _show_planning_page(self) -> None:
        self.page_stack.setCurrentIndex(self.PLANNING_PAGE_INDEX)
        self.statusBar().showMessage("Book setup", 2000)

    def _show_output_page(self) -> None:
        if self.current_imposition is None:
            QMessageBox.warning(
                self,
                "Signature Plan Required",
                (
                    "The book needs a valid signature plan before "
                    "continuing to print setup and export."
                ),
            )
            return

        self._refresh_pdf_preview_summary()
        self.page_stack.setCurrentIndex(self.OUTPUT_PAGE_INDEX)
        self.statusBar().showMessage("Print setup and export", 2000)

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
            self.statusBar().showMessage(
                ", ".join(status_parts),
                5000,
            )

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

        self.statusBar().showMessage(
            "Blank pages updated",
            3000,
        )

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

    def _choose_output_directory(self) -> None:
        current_directory = self.project.output_directory

        if not current_directory.exists():
            current_directory = Path.home()

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Signature Output Folder",
            str(current_directory),
        )

        if not selected_directory:
            return

        self.project.output_directory = Path(selected_directory)
        self.last_export_directory = None

        self._refresh_export_controls()
        self._refresh_summary()

        self.statusBar().showMessage(
            f"Output folder set to {selected_directory}",
            4000,
        )

    def _export_signatures(self) -> None:
        self._apply_print_settings()

        if self.separate_duplex_outputs:
            QMessageBox.information(
                self,
                "Separate Duplex Output",
                (
                    "The separate A-side and B-side option is part of "
                    "the new interface, but separate-file generation "
                    "has not been connected yet.\n\n"
                    "The current export will generate ordinary duplex "
                    "signature PDFs."
                ),
            )

        sequence_value = self.signature_sequence_edit.text()

        try:
            sheet_counts = SignaturePlanner.parse_signature_sequence(sequence_value)

            self.project.signature_sheet_counts = list(sheet_counts)

            plan = SignaturePlanner.create(
                self.project,
                sheet_counts=sheet_counts,
            )

            stream = LogicalPageStreamBuilder.create(self.project)
            imposition = BookletImposer.create(plan)

            result = SignaturePdfExporter.export(
                self.project,
                stream,
                imposition,
                output_directory=self.project.output_directory,
            )
        except (
            SignaturePlanError,
            LogicalPageStreamError,
            BookletImpositionError,
            SignaturePdfExportError,
        ) as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                str(exc),
            )
            self.statusBar().showMessage("Export failed", 5000)
            return
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"The output folder could not be used:\n\n{exc}",
            )
            self.statusBar().showMessage("Export failed", 5000)
            return

        self.current_imposition = imposition
        self.last_export_directory = result.output_directory

        self._refresh_export_controls()
        self._refresh_pdf_preview_summary()

        signature_word = "signature" if result.signature_count == 1 else "signatures"
        sheet_word = "sheet" if result.total_sheet_count == 1 else "sheets"

        QMessageBox.information(
            self,
            "Export Complete",
            (
                f"Exported {result.signature_count} {signature_word} "
                f"covering {result.total_sheet_count} {sheet_word}.\n\n"
                f"Output folder:\n{result.output_directory}\n\n"
                "Print the generated PDFs double-sided at 100% scale, "
                "flipping on the short edge. Do not enable the printer's "
                "booklet mode."
            ),
        )

        self.statusBar().showMessage(
            (f"Exported {result.signature_count} {signature_word} to {result.output_directory}"),
            8000,
        )

    def _open_output_directory(self) -> None:
        directory = self.last_export_directory

        if directory is None:
            directory = self.project.output_directory

        if not directory.exists():
            QMessageBox.warning(
                self,
                "Output Folder Not Found",
                (f"The output folder does not currently exist:\n\n{directory}"),
            )
            self._refresh_export_controls()
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))

        if not opened:
            QMessageBox.warning(
                self,
                "Could Not Open Folder",
                (f"The output folder could not be opened automatically:\n\n{directory}"),
            )

    def _duplex_output_changed(self, state: int) -> None:
        self.separate_duplex_outputs = state == Qt.CheckState.Checked.value
        self.last_export_directory = None
        self._refresh_pdf_preview_summary()

    def _print_settings_changed(self) -> None:
        self._apply_print_settings()
        self.last_export_directory = None
        self._refresh_export_controls()
        self._refresh_pdf_preview_summary()

    def _apply_print_settings(self) -> None:
        self.project.print_settings.margins.binding_mm = self.binding_margin_spin.value()
        self.project.print_settings.margins.outer_mm = self.outer_margin_spin.value()
        self.project.print_settings.margins.top_mm = self.top_margin_spin.value()
        self.project.print_settings.margins.bottom_mm = self.bottom_margin_spin.value()

        selected_paper_size = self.paper_size_combo.currentData()

        if isinstance(selected_paper_size, PaperSize):
            self.project.print_settings.paper_size = selected_paper_size

        selected_fitting_mode = self.fitting_mode_combo.currentData()

        if isinstance(selected_fitting_mode, PageFittingMode):
            self.project.print_settings.fitting_mode = selected_fitting_mode

    def _signature_sequence_changed(self, value: str) -> None:
        self.last_export_directory = None

        try:
            sheet_counts = SignaturePlanner.parse_signature_sequence(value)
        except SignaturePlanError:
            self.project.signature_sheet_counts = []
        else:
            self.project.signature_sheet_counts = list(sheet_counts)

        self._refresh_summary()
        self._refresh_signature_plan()

    def _selected_signature_changed(
        self,
        selected_index: int,
    ) -> None:
        if (
            self.current_imposition is None
            or selected_index < 0
            or selected_index >= len(self.current_imposition.signatures)
        ):
            self._clear_sheet_preview()
            return

        signature = self.current_imposition.signatures[selected_index]
        self._show_signature_preview(signature)

    def _refresh_interface(self) -> None:
        self.last_export_directory = None

        self._refresh_input_list()
        self._refresh_summary()
        self._refresh_signature_plan()
        self._refresh_export_controls()
        self._refresh_pdf_preview_summary()
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
            self.input_list.setCurrentRow(
                min(
                    selected_index,
                    len(self.project.inputs) - 1,
                )
            )

    def _refresh_summary(self) -> None:
        pdf_count = len(self.project.documents)
        input_count = len(self.project.inputs)

        duplex_description = (
            "Separate A/B files" if self.separate_duplex_outputs else "Ordinary duplex PDF"
        )

        self.summary_label.setText(
            f"<b>Book name</b><br>"
            f"{self.project.name}<br><br>"
            f"<b>Inputs</b><br>"
            f"Input entries: {input_count}<br>"
            f"PDF documents: {pdf_count}<br>"
            f"PDF pages: "
            f"{self.project.source_pdf_page_count}<br>"
            f"Blank pages: {self.project.blank_page_count}<br>"
            f"Total pages: {self.project.total_page_count}<br><br>"
            f"<b>Signatures</b><br>"
            f"Defined signatures: "
            f"{self.project.signature_count}<br>"
            f"Signature capacity: "
            f"{self.project.signature_page_capacity} pages<br><br>"
            f"<b>Duplex mode</b><br>"
            f"{duplex_description}<br><br>"
            f"<b>Output</b><br>"
            f"{self.project.output_directory}"
        )

    def _refresh_signature_plan(self) -> None:
        selected_signature_index = self.signature_list.currentRow()

        self.signature_list.blockSignals(True)
        self.signature_list.clear()
        self.signature_list.blockSignals(False)

        self.current_imposition = None
        self._clear_sheet_preview()
        self._refresh_navigation_controls()
        self._refresh_export_controls()

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

        try:
            imposition = BookletImposer.create(plan)
        except BookletImpositionError as exc:
            self._show_warning_validation(
                f"The signature plan is valid, but imposition failed: {exc}"
            )
            self.plan_summary_label.setText(
                f"Input: {plan.total_page_count} pages · {plan.total_sheet_count} sheets"
            )
            return

        self.current_imposition = imposition

        self._show_valid_validation(
            "The plan exactly covers the ordered input pages and has been imposed successfully."
        )

        self.plan_summary_label.setText(
            f"<b>{plan.signature_count} signatures</b> · "
            f"{plan.total_sheet_count} sheets · "
            f"{plan.total_page_count} pages<br>"
            f"PDF pages: {plan.source_pdf_page_count} · "
            f"Blank pages: {plan.blank_page_count}"
        )

        self.signature_list.blockSignals(True)

        for signature in plan.signatures:
            sheet_word = "sheet" if signature.sheet_count == 1 else "sheets"

            self.signature_list.addItem(
                f"Signature {signature.number} — "
                f"{signature.sheet_count} {sheet_word} / "
                f"{signature.page_count} pages — "
                f"Book pages "
                f"{signature.start_page_index + 1}"
                f"–{signature.end_page_index + 1}"
            )

        self.signature_list.blockSignals(False)

        if self.signature_list.count() > 0:
            if selected_signature_index < 0:
                selected_signature_index = 0

            selected_signature_index = min(
                selected_signature_index,
                self.signature_list.count() - 1,
            )

            self.signature_list.setCurrentRow(selected_signature_index)

        self._refresh_navigation_controls()
        self._refresh_export_controls()
        self._refresh_pdf_preview_summary()

    def _refresh_navigation_controls(self) -> None:
        self.next_button.setEnabled(self.current_imposition is not None)

    def _refresh_export_controls(self) -> None:
        output_directory = self.project.output_directory

        self.output_directory_label.setText(f"<b>Output folder</b><br>{output_directory}")

        self.export_button.setEnabled(self.current_imposition is not None)

        directory_to_open = (
            self.last_export_directory
            if self.last_export_directory is not None
            else output_directory
        )

        self.open_output_button.setEnabled(directory_to_open.exists())

    def _refresh_pdf_preview_summary(self) -> None:
        if self.current_imposition is None:
            self.pdf_preview_summary_label.setText(
                "A valid signature plan is required before previewing output."
            )
            return

        paper_size = self._enum_display_name(self.project.print_settings.paper_size)
        fitting_mode = self._enum_display_name(self.project.print_settings.fitting_mode)
        duplex_mode = "Separate A/B files" if self.separate_duplex_outputs else "Ordinary duplex"

        self.pdf_preview_summary_label.setText(
            f"<b>{self.current_imposition.signature_count} "
            f"signatures</b> · "
            f"{self.current_imposition.total_sheet_count} sheets · "
            f"{paper_size} landscape · "
            f"{fitting_mode} · "
            f"{duplex_mode}"
        )

    def _show_signature_preview(
        self,
        signature: ImposedSignature,
    ) -> None:
        self.sheet_preview_list.clear()

        sheet_word = "sheet" if signature.sheet_count == 1 else "sheets"

        self.selected_signature_summary_label.setText(
            f"<b>Signature {signature.number}</b><br>"
            f"{signature.sheet_count} {sheet_word}<br>"
            f"Pages {signature.start_page_index + 1}"
            f"–{signature.end_page_index + 1}"
        )

        for sheet in signature.sheets:
            self.sheet_preview_list.addItem(
                f"Sheet {sheet.number}\n"
                f"F: {sheet.front.left_page_number} | "
                f"{sheet.front.right_page_number}\n"
                f"B: {sheet.back.left_page_number} | "
                f"{sheet.back.right_page_number}"
            )

    def _clear_sheet_preview(self) -> None:
        self.sheet_preview_list.clear()
        self.selected_signature_summary_label.setText("Select a valid signature.")

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

    @staticmethod
    def _enum_display_name(value: object) -> str:
        raw_value = getattr(value, "value", str(value))

        return str(raw_value).replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _select_combo_data(
        combo: QComboBox,
        target_value: object,
    ) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return

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
