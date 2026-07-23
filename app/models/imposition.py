"""Models representing booklet-imposed sheets and sides."""

from dataclasses import dataclass
from enum import StrEnum


class SheetSide(StrEnum):
    """The printable side of a physical sheet."""

    FRONT = "front"
    BACK = "back"


@dataclass(frozen=True, slots=True)
class ImposedSide:
    """Two logical book pages placed on one side of a sheet."""

    side: SheetSide
    left_page_index: int
    right_page_index: int

    @property
    def left_page_number(self) -> int:
        """Return the one-based left book page number."""

        return self.left_page_index + 1

    @property
    def right_page_number(self) -> int:
        """Return the one-based right book page number."""

        return self.right_page_index + 1

    @property
    def page_indices(self) -> tuple[int, int]:
        """Return both zero-based page indices."""

        return self.left_page_index, self.right_page_index

    @property
    def page_numbers(self) -> tuple[int, int]:
        """Return both one-based page numbers."""

        return self.left_page_number, self.right_page_number


@dataclass(frozen=True, slots=True)
class ImposedSheet:
    """One physical sheet within a signature."""

    number: int
    front: ImposedSide
    back: ImposedSide

    @property
    def page_indices(self) -> tuple[int, int, int, int]:
        """Return every logical page placed on this sheet."""

        return (
            self.front.left_page_index,
            self.front.right_page_index,
            self.back.left_page_index,
            self.back.right_page_index,
        )

    @property
    def page_numbers(self) -> tuple[int, int, int, int]:
        """Return every one-based page number placed on this sheet."""

        return (
            self.front.left_page_number,
            self.front.right_page_number,
            self.back.left_page_number,
            self.back.right_page_number,
        )


@dataclass(frozen=True, slots=True)
class ImposedSignature:
    """All imposed sheets belonging to one signature."""

    number: int
    start_page_index: int
    end_page_index: int
    sheets: tuple[ImposedSheet, ...]

    @property
    def sheet_count(self) -> int:
        """Return the number of physical sheets."""

        return len(self.sheets)

    @property
    def page_count(self) -> int:
        """Return the number of logical pages in the signature."""

        return self.end_page_index - self.start_page_index + 1

    @property
    def page_indices(self) -> tuple[int, ...]:
        """Return all page indices used by the imposed signature."""

        return tuple(page_index for sheet in self.sheets for page_index in sheet.page_indices)


@dataclass(frozen=True, slots=True)
class BookImposition:
    """Complete imposed sheet structure for a book."""

    signatures: tuple[ImposedSignature, ...]

    @property
    def signature_count(self) -> int:
        """Return the number of signatures."""

        return len(self.signatures)

    @property
    def total_sheet_count(self) -> int:
        """Return the number of physical sheets."""

        return sum(signature.sheet_count for signature in self.signatures)

    @property
    def total_page_count(self) -> int:
        """Return the number of logical book pages."""

        return sum(signature.page_count for signature in self.signatures)

    @property
    def page_indices(self) -> tuple[int, ...]:
        """Return every page index used across the complete book."""

        return tuple(
            page_index for signature in self.signatures for page_index in signature.page_indices
        )
