"""Models representing an explicit calculated signature plan."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlannedSignature:
    """One user-defined signature in the book."""

    number: int
    sheet_count: int
    page_count: int
    start_page_index: int
    end_page_index: int


@dataclass(frozen=True, slots=True)
class SignaturePlan:
    """Complete validated signature structure for a book."""

    source_pdf_page_count: int
    blank_page_count: int
    total_page_count: int
    signatures: tuple[PlannedSignature, ...]

    @property
    def signature_count(self) -> int:
        """Return the number of signatures."""

        return len(self.signatures)

    @property
    def total_sheet_count(self) -> int:
        """Return the total number of physical sheets."""

        return sum(signature.sheet_count for signature in self.signatures)

    @property
    def total_signature_page_capacity(self) -> int:
        """Return the pages covered by every signature."""

        return sum(signature.page_count for signature in self.signatures)
