"""Models representing the ordered logical pages of a book."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceLogicalPage:
    """One logical book page originating from a source PDF."""

    book_page_index: int
    document_path: Path
    document_page_index: int
    input_index: int

    @property
    def book_page_number(self) -> int:
        """Return the one-based page number within the complete book."""

        return self.book_page_index + 1

    @property
    def document_page_number(self) -> int:
        """Return the one-based page number within the source PDF."""

        return self.document_page_index + 1

    @property
    def filename(self) -> str:
        """Return the source PDF filename."""

        return self.document_path.name

    @property
    def is_blank(self) -> bool:
        """Return whether this logical page is blank."""

        return False


@dataclass(frozen=True, slots=True)
class BlankLogicalPage:
    """One explicitly inserted blank logical book page."""

    book_page_index: int
    input_index: int
    blank_index: int

    @property
    def book_page_number(self) -> int:
        """Return the one-based page number within the complete book."""

        return self.book_page_index + 1

    @property
    def blank_number(self) -> int:
        """Return the one-based position inside its blank-page block."""

        return self.blank_index + 1

    @property
    def is_blank(self) -> bool:
        """Return whether this logical page is blank."""

        return True


type LogicalPage = SourceLogicalPage | BlankLogicalPage


@dataclass(frozen=True, slots=True)
class LogicalPageStream:
    """The complete ordered logical page sequence for a book."""

    pages: tuple[LogicalPage, ...]

    def __len__(self) -> int:
        """Return the number of logical pages."""

        return len(self.pages)

    def __iter__(self):
        """Iterate over logical pages in book order."""

        return iter(self.pages)

    def __getitem__(self, index: int) -> LogicalPage:
        """Return a logical page by zero-based book index."""

        return self.pages[index]

    @property
    def page_count(self) -> int:
        """Return the total number of logical pages."""

        return len(self.pages)

    @property
    def source_page_count(self) -> int:
        """Return the number of pages originating from PDFs."""

        return sum(isinstance(page, SourceLogicalPage) for page in self.pages)

    @property
    def blank_page_count(self) -> int:
        """Return the number of explicit blank pages."""

        return sum(isinstance(page, BlankLogicalPage) for page in self.pages)
