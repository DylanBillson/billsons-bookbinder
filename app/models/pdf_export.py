"""Models representing generated imposed PDF files."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExportedSignaturePdf:
    """One generated imposed signature PDF."""

    signature_number: int
    sheet_count: int
    output_page_count: int
    path: Path


@dataclass(frozen=True, slots=True)
class PdfExportResult:
    """Complete result of exporting an imposed book."""

    output_directory: Path
    signatures: tuple[ExportedSignaturePdf, ...]

    @property
    def signature_count(self) -> int:
        """Return the number of generated signature files."""

        return len(self.signatures)

    @property
    def total_sheet_count(self) -> int:
        """Return the total number of physical sheets."""

        return sum(signature.sheet_count for signature in self.signatures)

    @property
    def total_output_page_count(self) -> int:
        """Return the total number of generated PDF pages."""

        return sum(signature.output_page_count for signature in self.signatures)

    @property
    def paths(self) -> tuple[Path, ...]:
        """Return every generated PDF path."""

        return tuple(signature.path for signature in self.signatures)
