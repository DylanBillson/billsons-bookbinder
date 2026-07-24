"""Central in-memory model for the current bookbinding project."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class PaperSize(StrEnum):
    """Supported physical printing sheet sizes."""

    A3 = "A3"
    A4 = "A4"
    A5 = "A5"


class PageFittingMode(StrEnum):
    """How source pages are placed inside their available area."""

    FIT = "fit"
    FILL_AND_CROP = "fill_and_crop"


class DuplexMode(StrEnum):
    """How generated signature files are intended to be printed."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"


@dataclass(slots=True)
class InputDocument:
    """A PDF included in the ordered book input sequence."""

    path: Path
    page_count: int

    @property
    def filename(self) -> str:
        """Return the filename including its extension."""

        return self.path.name

    @property
    def stem(self) -> str:
        """Return the filename without its extension."""

        return self.path.stem


@dataclass(slots=True)
class BlankPages:
    """One ordered block of blank pages."""

    quantity: int

    @property
    def page_count(self) -> int:
        """Return the number of blank pages in the block."""

        return self.quantity


type BookInput = InputDocument | BlankPages


@dataclass(slots=True)
class MarginSettings:
    """Margins applied to each finished book page in millimetres."""

    binding_mm: float = 10.0
    outer_mm: float = 5.0
    top_mm: float = 5.0
    bottom_mm: float = 5.0


@dataclass(slots=True)
class PrintSettings:
    """Physical sheet, page-placement and duplex settings."""

    paper_size: PaperSize = PaperSize.A4
    fitting_mode: PageFittingMode = PageFittingMode.FIT
    margins: MarginSettings = field(default_factory=MarginSettings)
    duplex_mode: DuplexMode = DuplexMode.AUTOMATIC


@dataclass(slots=True)
class BookProject:
    """Complete in-memory state for the currently open book."""

    name: str = "untitled-book"
    inputs: list[BookInput] = field(default_factory=list)
    signature_sheet_counts: list[int] = field(default_factory=list)
    print_settings: PrintSettings = field(default_factory=PrintSettings)

    output_root: Path = field(default_factory=lambda: Path("output"))

    combine_signatures: bool = False
    include_separator_sheets: bool = False

    @property
    def documents(self) -> list[InputDocument]:
        """Return all input PDFs in their current book order."""

        return [item for item in self.inputs if isinstance(item, InputDocument)]

    @property
    def source_pdf_page_count(self) -> int:
        """Return the combined page count of all input PDFs."""

        return sum(document.page_count for document in self.documents)

    @property
    def blank_page_count(self) -> int:
        """Return the number of explicitly inserted blank pages."""

        return sum(item.quantity for item in self.inputs if isinstance(item, BlankPages))

    @property
    def total_page_count(self) -> int:
        """Return the complete ordered input page count."""

        return sum(item.page_count for item in self.inputs)

    @property
    def signature_count(self) -> int:
        """Return the number of explicitly defined signatures."""

        return len(self.signature_sheet_counts)

    @property
    def signature_sheet_count(self) -> int:
        """Return the total sheets covered by the signature definition."""

        return sum(self.signature_sheet_counts)

    @property
    def signature_page_capacity(self) -> int:
        """Return the pages covered by the signature definition."""

        return self.signature_sheet_count * 4

    @property
    def output_directory(self) -> Path:
        """Return the intended output directory."""

        return self.output_root / self.name

    def add_document(
        self,
        document: InputDocument,
        *,
        index: int | None = None,
    ) -> bool:
        """Add a PDF unless the same file is already included."""

        if any(existing.path == document.path for existing in self.documents):
            return False

        self._insert_input(document, index=index)
        self._refresh_default_name()
        return True

    def add_blank_pages(
        self,
        quantity: int,
        *,
        index: int | None = None,
    ) -> BlankPages:
        """Insert a block of blank pages into the input sequence."""

        if quantity < 1:
            raise ValueError("Blank-page quantity must be at least 1.")

        blank_pages = BlankPages(quantity=quantity)
        self._insert_input(blank_pages, index=index)
        return blank_pages

    def edit_blank_pages(self, index: int, quantity: int) -> None:
        """Change the quantity of an existing blank-page block."""

        if quantity < 1:
            raise ValueError("Blank-page quantity must be at least 1.")

        item = self.inputs[index]

        if not isinstance(item, BlankPages):
            raise TypeError("The selected input is not a blank-page block.")

        item.quantity = quantity

    def remove_input(self, index: int) -> BookInput:
        """Remove and return an item from the input sequence."""

        item = self.inputs.pop(index)
        self._refresh_default_name()
        return item

    def move_input(self, old_index: int, new_index: int) -> None:
        """Move an input item to another position."""

        if old_index == new_index:
            return

        item = self.inputs.pop(old_index)
        self.inputs.insert(new_index, item)
        self._refresh_default_name()

    def _insert_input(
        self,
        item: BookInput,
        *,
        index: int | None,
    ) -> None:
        """Insert an input at an index or append it."""

        if index is None:
            self.inputs.append(item)
            return

        bounded_index = max(0, min(index, len(self.inputs)))
        self.inputs.insert(bounded_index, item)

    def _refresh_default_name(self) -> None:
        """Set the output name from the first PDF in book order."""

        first_document = next(
            (item for item in self.inputs if isinstance(item, InputDocument)),
            None,
        )

        if first_document is None:
            self.name = "untitled-book"
            return

        self.name = self._normalise_book_name(first_document.stem)

    @staticmethod
    def _normalise_book_name(value: str) -> str:
        """Convert a filename stem into a safe default output name."""

        normalised = value.strip().lower().replace(" ", "-").replace("_", "-")

        normalised = "".join(
            character for character in normalised if character.isalnum() or character == "-"
        )

        while "--" in normalised:
            normalised = normalised.replace("--", "-")

        return normalised.strip("-") or "untitled-book"
