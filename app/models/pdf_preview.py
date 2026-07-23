"""Models representing rendered PDF previews."""

from dataclasses import dataclass

from app.models.imposition import SheetSide


@dataclass(frozen=True, slots=True)
class RenderedPreviewPage:
    """One rendered side of an imposed physical sheet."""

    signature_number: int
    sheet_number: int
    side: SheetSide
    output_page_index: int
    left_page_number: int
    right_page_number: int
    width_pixels: int
    height_pixels: int
    png_bytes: bytes

    @property
    def label(self) -> str:
        """Return a human-readable preview label."""

        side_name = self.side.value.title()

        return f"Signature {self.signature_number}, Sheet {self.sheet_number}, {side_name}"


@dataclass(frozen=True, slots=True)
class SignaturePreview:
    """Rendered preview pages for one imposed signature."""

    signature_number: int
    sheet_count: int
    pages: tuple[RenderedPreviewPage, ...]

    @property
    def page_count(self) -> int:
        """Return the number of rendered sheet sides."""

        return len(self.pages)

    @property
    def expected_page_count(self) -> int:
        """Return the expected number of rendered sides."""

        return self.sheet_count * 2

    def page(self, index: int) -> RenderedPreviewPage:
        """Return one preview page by its zero-based output index."""

        try:
            return self.pages[index]
        except IndexError as exc:
            raise IndexError(
                f"Preview page index {index} is outside the range 0–{len(self.pages) - 1}."
            ) from exc


@dataclass(frozen=True, slots=True)
class BookPreview:
    """Rendered previews for every imposed signature."""

    signatures: tuple[SignaturePreview, ...]

    @property
    def signature_count(self) -> int:
        """Return the number of rendered signatures."""

        return len(self.signatures)

    @property
    def page_count(self) -> int:
        """Return the total number of rendered sheet sides."""

        return sum(signature.page_count for signature in self.signatures)

    def signature(self, signature_number: int) -> SignaturePreview:
        """Return a signature preview by its one-based number."""

        for signature in self.signatures:
            if signature.signature_number == signature_number:
                return signature

        raise KeyError(f"No preview exists for signature {signature_number}.")
