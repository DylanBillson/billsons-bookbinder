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


class IncompleteSignatureMode(StrEnum):
    """How a signature smaller than the normal size is handled."""

    ADD_BLANKS = "add_blanks"
    SMALLER_SIGNATURE = "smaller_signature"


class SmallerSignaturePosition(StrEnum):
    """Placement of a smaller signature within the book."""

    BEGINNING = "beginning"
    MIDDLE = "middle"
    END = "end"


@dataclass(slots=True)
class InputDocument:
    """A PDF selected as part of the current book."""

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
    sheets_per_signature: int = 4
    fitting_mode: PageFittingMode = PageFittingMode.FIT
    margins: MarginSettings = field(default_factory=MarginSettings)
    duplex_mode: DuplexMode = DuplexMode.AUTOMATIC
    rotate_reverse_sides: bool = True


@dataclass(slots=True)
class SignatureSettings:
    """Rules for blank pages and incomplete signatures."""

    handling: IncompleteSignatureMode = IncompleteSignatureMode.ADD_BLANKS
    blank_pages_start: int = 0
    blank_pages_end: int = 0
    smaller_signature_position: SmallerSignaturePosition = SmallerSignaturePosition.END


@dataclass(slots=True)
class BookProject:
    """Complete in-memory state for the current book."""

    name: str = "untitled-book"
    documents: list[InputDocument] = field(default_factory=list)
    print_settings: PrintSettings = field(default_factory=PrintSettings)
    signature_settings: SignatureSettings = field(default_factory=SignatureSettings)
    output_root: Path = field(default_factory=lambda: Path("output"))

    @property
    def source_page_count(self) -> int:
        """Return the total number of pages across all input PDFs."""

        return sum(document.page_count for document in self.documents)

    @property
    def pages_per_signature(self) -> int:
        """Return the normal number of pages in one signature."""

        return self.print_settings.sheets_per_signature * 4

    @property
    def blank_page_count(self) -> int:
        """Return the total number of explicitly added blank pages."""

        return self.signature_settings.blank_pages_start + self.signature_settings.blank_pages_end

    @property
    def total_page_count(self) -> int:
        """Return the source and explicitly added page total."""

        return self.source_page_count + self.blank_page_count

    @property
    def output_directory(self) -> Path:
        """Return the intended output directory for the project."""

        return self.output_root / self.name

    def add_document(self, document: InputDocument) -> bool:
        """Add a document unless the same file is already present."""

        if any(existing.path == document.path for existing in self.documents):
            return False

        self.documents.append(document)

        if len(self.documents) == 1:
            self.name = self._normalise_book_name(document.stem)

        return True

    def remove_document(self, index: int) -> InputDocument:
        """Remove and return the document at an index."""

        document = self.documents.pop(index)

        if self.documents:
            self.name = self._normalise_book_name(self.documents[0].stem)
        else:
            self.name = "untitled-book"

        return document

    def move_document(self, old_index: int, new_index: int) -> None:
        """Move a document to another position."""

        if old_index == new_index:
            return

        document = self.documents.pop(old_index)
        self.documents.insert(new_index, document)

        if self.documents:
            self.name = self._normalise_book_name(self.documents[0].stem)

    @staticmethod
    def _normalise_book_name(value: str) -> str:
        """Convert a filename stem into a safe default output name."""

        normalised = value.strip().lower()

        for character in (" ", "_"):
            normalised = normalised.replace(character, "-")

        safe_characters = {
            character for character in normalised if character.isalnum() or character == "-"
        }

        normalised = "".join(character for character in normalised if character in safe_characters)

        while "--" in normalised:
            normalised = normalised.replace("--", "-")

        return normalised.strip("-") or "untitled-book"
