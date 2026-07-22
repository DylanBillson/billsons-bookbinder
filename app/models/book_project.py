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
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass(slots=True)
class MarginSettings:
    """Margins applied to each finished book page, measured in millimetres."""

    binding_mm: float = 10.0
    outer_mm: float = 5.0
    top_mm: float = 5.0
    bottom_mm: float = 5.0


@dataclass(slots=True)
class PrintSettings:
    """Physical sheet, page placement and duplex settings."""

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
    smaller_signature_position: SmallerSignaturePosition = (
        SmallerSignaturePosition.END
    )


@dataclass(slots=True)
class BookProject:
    """Complete in-memory state for the currently open book."""

    name: str = "untitled-book"
    documents: list[InputDocument] = field(default_factory=list)
    print_settings: PrintSettings = field(default_factory=PrintSettings)
    signature_settings: SignatureSettings = field(
        default_factory=SignatureSettings
    )
    output_root: Path = field(default_factory=lambda: Path("output"))

    @property
    def source_page_count(self) -> int:
        return sum(document.page_count for document in self.documents)

    @property
    def pages_per_signature(self) -> int:
        return self.print_settings.sheets_per_signature * 4

    @property
    def blank_page_count(self) -> int:
        return (
            self.signature_settings.blank_pages_start
            + self.signature_settings.blank_pages_end
        )

    @property
    def total_page_count(self) -> int:
        return self.source_page_count + self.blank_page_count

    @property
    def output_directory(self) -> Path:
        return self.output_root / self.name