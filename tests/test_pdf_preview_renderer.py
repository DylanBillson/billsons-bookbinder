"""Tests for imposed PDF preview rendering."""

from pathlib import Path

import pymupdf
import pytest

from app.core import (
    BookletImposer,
    LogicalPageStreamBuilder,
    SignaturePlanner,
)
from app.models import (
    BlankPages,
    BookProject,
    InputDocument,
    PageFittingMode,
    PaperSize,
    SheetSide,
)
from app.services import (
    PdfPreviewRenderer,
    PdfPreviewRenderError,
)


def create_labelled_pdf(
    path: Path,
    page_count: int,
    *,
    width: float = 420,
    height: float = 595,
) -> None:
    """Create a synthetic PDF with one label per source page."""

    document = pymupdf.open()

    try:
        for page_number in range(1, page_count + 1):
            page = document.new_page(
                width=width,
                height=height,
            )

            page.insert_text(
                (72, 100),
                f"SOURCE-PAGE-{page_number}",
                fontsize=18,
            )

        document.save(path)
    finally:
        document.close()


def create_render_structures(
    project: BookProject,
):
    """Create the logical stream and imposed book."""

    plan = SignaturePlanner.create(project)
    stream = LogicalPageStreamBuilder.create(project)
    imposition = BookletImposer.create(plan)

    return stream, imposition


def open_png_document(png_bytes: bytes) -> pymupdf.Document:
    """Open rendered PNG bytes as an image document."""

    return pymupdf.open(
        stream=png_bytes,
        filetype="png",
    )


def test_render_signature_returns_two_pages_per_sheet(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 16)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=16,
            )
        ],
        signature_sheet_counts=[4],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    assert preview.signature_number == 1
    assert preview.sheet_count == 4
    assert preview.page_count == 8
    assert preview.expected_page_count == 8


def test_preview_pages_follow_duplex_output_order(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 8)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=8,
            )
        ],
        signature_sheet_counts=[2],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    assert [
        (
            page.sheet_number,
            page.side,
            page.left_page_number,
            page.right_page_number,
        )
        for page in preview.pages
    ] == [
        (1, SheetSide.FRONT, 8, 1),
        (1, SheetSide.BACK, 2, 7),
        (2, SheetSide.FRONT, 6, 3),
        (2, SheetSide.BACK, 4, 5),
    ]


def test_preview_contains_valid_png_bytes(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    rendered_page = preview.pages[0]

    assert rendered_page.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert rendered_page.width_pixels > 0
    assert rendered_page.height_pixels > 0

    image_document = open_png_document(rendered_page.png_bytes)

    try:
        assert image_document.page_count == 1
    finally:
        image_document.close()


def test_landscape_preview_is_wider_than_tall(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    rendered_page = preview.pages[0]

    assert rendered_page.width_pixels > rendered_page.height_pixels


@pytest.mark.parametrize(
    "paper_size",
    [
        PaperSize.A3,
        PaperSize.A4,
        PaperSize.A5,
    ],
)
def test_supported_paper_sizes_render(
    tmp_path: Path,
    paper_size: PaperSize,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )
    project.print_settings.paper_size = paper_size

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
        dpi=72,
    )

    assert preview.page_count == 2
    assert all(page.width_pixels > 0 for page in preview.pages)
    assert all(page.height_pixels > 0 for page in preview.pages)


def test_higher_dpi_produces_larger_preview(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    low_resolution = PdfPreviewRenderer.render_page(
        project,
        stream,
        imposition,
        signature_number=1,
        output_page_index=0,
        dpi=72,
    )

    high_resolution = PdfPreviewRenderer.render_page(
        project,
        stream,
        imposition,
        signature_number=1,
        output_page_index=0,
        dpi=144,
    )

    assert high_resolution.width_pixels > low_resolution.width_pixels
    assert high_resolution.height_pixels > low_resolution.height_pixels


def test_render_one_page_returns_requested_side(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 8)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=8,
            )
        ],
        signature_sheet_counts=[2],
    )

    stream, imposition = create_render_structures(project)

    rendered_page = PdfPreviewRenderer.render_page(
        project,
        stream,
        imposition,
        signature_number=1,
        output_page_index=1,
    )

    assert rendered_page.sheet_number == 1
    assert rendered_page.side is SheetSide.BACK
    assert rendered_page.left_page_number == 2
    assert rendered_page.right_page_number == 7


def test_render_book_returns_every_signature(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 24)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=24,
            )
        ],
        signature_sheet_counts=[4, 2],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_book(
        project,
        stream,
        imposition,
    )

    assert preview.signature_count == 2
    assert preview.page_count == 12

    assert preview.signatures[0].page_count == 8
    assert preview.signatures[1].page_count == 4


def test_explicit_blank_page_renders_successfully(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 3)

    project = BookProject(
        inputs=[
            BlankPages(quantity=1),
            InputDocument(
                path=source_path,
                page_count=3,
            ),
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    assert preview.page_count == 2
    assert preview.pages[0].left_page_number == 4
    assert preview.pages[0].right_page_number == 1


def test_fill_and_crop_mode_renders(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "wide.pdf"

    create_labelled_pdf(
        source_path,
        4,
        width=800,
        height=400,
    )

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )
    project.print_settings.fitting_mode = PageFittingMode.FILL_AND_CROP

    stream, imposition = create_render_structures(project)

    preview = PdfPreviewRenderer.render_signature(
        project,
        stream,
        imposition,
        signature_number=1,
    )

    assert preview.page_count == 2
    assert all(page.png_bytes for page in preview.pages)


@pytest.mark.parametrize(
    "dpi",
    [
        35,
        301,
    ],
)
def test_invalid_dpi_is_rejected(
    tmp_path: Path,
    dpi: int,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    with pytest.raises(
        PdfPreviewRenderError,
        match="DPI must be between",
    ):
        PdfPreviewRenderer.render_signature(
            project,
            stream,
            imposition,
            signature_number=1,
            dpi=dpi,
        )


def test_unknown_signature_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    with pytest.raises(
        PdfPreviewRenderError,
        match="No imposed signature has number 2",
    ):
        PdfPreviewRenderer.render_signature(
            project,
            stream,
            imposition,
            signature_number=2,
        )


def test_invalid_output_page_index_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    with pytest.raises(
        PdfPreviewRenderError,
        match="outside the valid range",
    ):
        PdfPreviewRenderer.render_page(
            project,
            stream,
            imposition,
            signature_number=1,
            output_page_index=2,
        )


def test_missing_source_file_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "missing.pdf"

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_render_structures(project)

    with pytest.raises(
        PdfPreviewRenderError,
        match="does not exist",
    ):
        PdfPreviewRenderer.render_signature(
            project,
            stream,
            imposition,
            signature_number=1,
        )
