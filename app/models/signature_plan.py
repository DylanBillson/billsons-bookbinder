"""Models representing a calculated signature plan."""

from dataclasses import dataclass
from enum import StrEnum


class SignatureKind(StrEnum):
    """The structural type of a signature."""

    FULL = "full"
    SMALLER = "smaller"


@dataclass(frozen=True, slots=True)
class PlannedSignature:
    """One signature in the calculated book structure."""

    number: int
    kind: SignatureKind
    sheet_count: int
    page_count: int
    start_page_index: int
    end_page_index: int

    @property
    def is_full(self) -> bool:
        """Return whether this is a normal full-size signature."""

        return self.kind is SignatureKind.FULL

    @property
    def is_smaller(self) -> bool:
        """Return whether this is the smaller incomplete signature."""

        return self.kind is SignatureKind.SMALLER


@dataclass(frozen=True, slots=True)
class SignaturePlan:
    """Complete calculated signature structure for a book."""

    source_page_count: int
    blank_pages_start: int
    blank_pages_end: int
    total_page_count: int
    normal_sheets_per_signature: int
    normal_pages_per_signature: int
    signatures: tuple[PlannedSignature, ...]

    @property
    def signature_count(self) -> int:
        """Return the total number of signatures."""

        return len(self.signatures)

    @property
    def total_sheet_count(self) -> int:
        """Return the total number of physical sheets."""

        return sum(signature.sheet_count for signature in self.signatures)

    @property
    def full_signature_count(self) -> int:
        """Return the number of normal full-size signatures."""

        return sum(signature.is_full for signature in self.signatures)

    @property
    def smaller_signature(self) -> PlannedSignature | None:
        """Return the smaller signature when one exists."""

        return next(
            (signature for signature in self.signatures if signature.is_smaller),
            None,
        )
