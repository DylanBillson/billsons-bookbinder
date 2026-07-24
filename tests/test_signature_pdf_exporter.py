"""Tests for imposed signature PDF generation."""

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
)
from app.services import (
    SignaturePdfExporter,
    SignaturePdfExportError,
)


def create_labelled_pdf(
    path: Path,
    page_count: int,
    *,
    width: float = 420,
    height: float = 595,
) -> None:
    """Create a synthetic PDF with a unique label on every page."""

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


def create_export_structures(
    project: BookProject,
):
    """Create the stream and imposition required by the exporter."""

    plan = SignaturePlanner.create(project)
    stream = LogicalPageStreamBuilder.create(project)
    imposition = BookletImposer.create(plan)

    return stream, imposition


def read_page_texts(path: Path) -> list[str]:
    """Extract text from every output page."""

    document = pymupdf.open(path)

    try:
        return [page.get_text() for page in document]
    finally:
        document.close()


def test_one_signature_pdf_is_created(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_export_structures(project)
    output_directory = tmp_path / "output"

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=output_directory,
    )

    expected_path = (
        output_directory
        / "1-signature-secret-garden.pdf"
    )

    assert result.signature_count == 1
    assert result.file_count == 1
    assert result.paths == (expected_path,)
    assert result.signatures[0].paths == (expected_path,)
    assert expected_path.exists()


def test_one_sheet_signature_has_two_output_pages(
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    output_document = pymupdf.open(result.paths[0])

    try:
        assert output_document.page_count == 2
    finally:
        output_document.close()


def test_one_sheet_signature_uses_correct_page_order(
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    page_texts = read_page_texts(result.paths[0])

    assert "SOURCE-PAGE-4" in page_texts[0]
    assert "SOURCE-PAGE-1" in page_texts[0]

    assert "SOURCE-PAGE-2" in page_texts[1]
    assert "SOURCE-PAGE-3" in page_texts[1]


def test_four_sheet_signature_uses_duplex_print_order(
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    page_texts = read_page_texts(result.paths[0])

    expected_pairs = [
        (16, 1),
        (2, 15),
        (14, 3),
        (4, 13),
        (12, 5),
        (6, 11),
        (10, 7),
        (8, 9),
    ]

    assert len(page_texts) == len(expected_pairs)

    for output_text, expected_pair in zip(
        page_texts,
        expected_pairs,
        strict=True,
    ):
        for source_page_number in expected_pair:
            assert (
                f"SOURCE-PAGE-{source_page_number}"
                in output_text
            )


def test_multiple_signatures_create_separate_files(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 24)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=24,
            )
        ],
        signature_sheet_counts=[4, 2],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    assert result.signature_count == 2
    assert result.file_count == 2
    assert result.total_sheet_count == 6
    assert result.total_output_page_count == 12

    assert result.paths == (
        (
            tmp_path
            / "output"
            / "1-signature-secret-garden.pdf"
        ),
        (
            tmp_path
            / "output"
            / "2-signature-secret-garden.pdf"
        ),
    )

    assert result.signatures[0].paths == (
        result.paths[0],
    )
    assert result.signatures[1].paths == (
        result.paths[1],
    )

    assert all(path.exists() for path in result.paths)


def test_second_signature_uses_correct_global_pages(
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    second_signature_texts = read_page_texts(
        result.paths[1]
    )

    assert (
        "SOURCE-PAGE-24"
        in second_signature_texts[0]
    )
    assert (
        "SOURCE-PAGE-17"
        in second_signature_texts[0]
    )

    assert (
        "SOURCE-PAGE-18"
        in second_signature_texts[1]
    )
    assert (
        "SOURCE-PAGE-23"
        in second_signature_texts[1]
    )


def test_explicit_blank_page_produces_empty_slot(
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    page_texts = read_page_texts(result.paths[0])

    # Booklet order is front 4 | 1, then back 2 | 3.
    assert "SOURCE-PAGE-3" in page_texts[0]
    assert "SOURCE-PAGE-1" not in page_texts[0]
    assert "SOURCE-PAGE-2" not in page_texts[0]

    assert "SOURCE-PAGE-1" in page_texts[1]
    assert "SOURCE-PAGE-2" in page_texts[1]


def test_37_page_example_outputs_expected_signature_three(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 37)

    project = BookProject(
        inputs=[
            BlankPages(quantity=1),
            InputDocument(
                path=source_path,
                page_count=37,
            ),
            BlankPages(quantity=2),
        ],
        signature_sheet_counts=[4, 4, 2],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    signature_three_texts = read_page_texts(
        result.paths[2]
    )

    assert len(signature_three_texts) == 4

    # Sheet 1 front: book 40 blank | book 33 = source 32.
    assert (
        "SOURCE-PAGE-32"
        in signature_three_texts[0]
    )

    # Sheet 1 back: book 34 = source 33 | book 39 blank.
    assert (
        "SOURCE-PAGE-33"
        in signature_three_texts[1]
    )

    # Sheet 2 front: book 38 = source 37 | book 35 = source 34.
    assert (
        "SOURCE-PAGE-37"
        in signature_three_texts[2]
    )
    assert (
        "SOURCE-PAGE-34"
        in signature_three_texts[2]
    )

    # Sheet 2 back: book 36 = source 35 | book 37 = source 36.
    assert (
        "SOURCE-PAGE-35"
        in signature_three_texts[3]
    )
    assert (
        "SOURCE-PAGE-36"
        in signature_three_texts[3]
    )


def test_separate_duplex_export_creates_a_and_b_files(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_export_structures(project)
    output_directory = tmp_path / "output"

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=output_directory,
        separate_duplex_outputs=True,
    )

    a_path = (
        output_directory
        / "1a-signature-secret-garden.pdf"
    )
    b_path = (
        output_directory
        / "1b-signature-secret-garden.pdf"
    )

    assert result.signature_count == 1
    assert result.file_count == 2
    assert result.total_sheet_count == 1
    assert result.total_output_page_count == 2

    assert result.paths == (
        a_path,
        b_path,
    )
    assert result.signatures[0].paths == (
        a_path,
        b_path,
    )

    assert a_path.exists()
    assert b_path.exists()


def test_separate_duplex_files_contain_one_page_per_sheet(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 16)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=16,
            )
        ],
        signature_sheet_counts=[4],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
        separate_duplex_outputs=True,
    )

    a_document = pymupdf.open(result.paths[0])
    b_document = pymupdf.open(result.paths[1])

    try:
        assert a_document.page_count == 4
        assert b_document.page_count == 4
    finally:
        a_document.close()
        b_document.close()


def test_separate_duplex_a_file_contains_all_fronts(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 16)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=16,
            )
        ],
        signature_sheet_counts=[4],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
        separate_duplex_outputs=True,
    )

    a_page_texts = read_page_texts(result.paths[0])

    expected_front_pairs = [
        (16, 1),
        (14, 3),
        (12, 5),
        (10, 7),
    ]

    assert len(a_page_texts) == 4

    for output_text, expected_pair in zip(
        a_page_texts,
        expected_front_pairs,
        strict=True,
    ):
        for source_page_number in expected_pair:
            assert (
                f"SOURCE-PAGE-{source_page_number}"
                in output_text
            )


def test_separate_duplex_b_file_contains_all_backs(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 16)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=16,
            )
        ],
        signature_sheet_counts=[4],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
        separate_duplex_outputs=True,
    )

    b_page_texts = read_page_texts(result.paths[1])

    expected_back_pairs = [
        (2, 15),
        (4, 13),
        (6, 11),
        (8, 9),
    ]

    assert len(b_page_texts) == 4

    for output_text, expected_pair in zip(
        b_page_texts,
        expected_back_pairs,
        strict=True,
    ):
        for source_page_number in expected_pair:
            assert (
                f"SOURCE-PAGE-{source_page_number}"
                in output_text
            )


def test_separate_duplex_multiple_signatures_create_four_files(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 24)

    project = BookProject(
        name="Secret Garden",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=24,
            )
        ],
        signature_sheet_counts=[4, 2],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
        separate_duplex_outputs=True,
    )

    assert result.signature_count == 2
    assert result.file_count == 4
    assert result.total_sheet_count == 6
    assert result.total_output_page_count == 12

    assert result.paths == (
        (
            tmp_path
            / "output"
            / "1a-signature-secret-garden.pdf"
        ),
        (
            tmp_path
            / "output"
            / "1b-signature-secret-garden.pdf"
        ),
        (
            tmp_path
            / "output"
            / "2a-signature-secret-garden.pdf"
        ),
        (
            tmp_path
            / "output"
            / "2b-signature-secret-garden.pdf"
        ),
    )

    assert result.signatures[0].paths == (
        result.paths[0],
        result.paths[1],
    )
    assert result.signatures[1].paths == (
        result.paths[2],
        result.paths[3],
    )

    assert all(path.exists() for path in result.paths)


def test_filename_uses_filesystem_friendly_book_name(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 4)

    project = BookProject(
        name="The Secret Garden: Illustrated Edition!",
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    assert result.paths == (
        (
            tmp_path
            / "output"
            / (
                "1-signature-"
                "the-secret-garden-illustrated-edition.pdf"
            )
        ),
    )


@pytest.mark.parametrize(
    (
        "paper_size",
        "expected_width_mm",
        "expected_height_mm",
    ),
    [
        (PaperSize.A3, 420.0, 297.0),
        (PaperSize.A4, 297.0, 210.0),
        (PaperSize.A5, 210.0, 148.0),
    ],
)
def test_output_uses_selected_landscape_paper_size(
    tmp_path: Path,
    paper_size: PaperSize,
    expected_width_mm: float,
    expected_height_mm: float,
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

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    output_document = pymupdf.open(result.paths[0])

    try:
        page_rect = output_document[0].rect
    finally:
        output_document.close()

    points_per_mm = 72.0 / 25.4

    assert page_rect.width == pytest.approx(
        expected_width_mm * points_per_mm,
        abs=0.1,
    )
    assert page_rect.height == pytest.approx(
        expected_height_mm * points_per_mm,
        abs=0.1,
    )


def test_fill_and_crop_mode_generates_output(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "wide-book.pdf"

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
    project.print_settings.fitting_mode = (
        PageFittingMode.FILL_AND_CROP
    )

    stream, imposition = create_export_structures(project)

    result = SignaturePdfExporter.export(
        project,
        stream,
        imposition,
        output_directory=tmp_path / "output",
    )

    assert result.paths[0].exists()

    output_document = pymupdf.open(result.paths[0])

    try:
        assert output_document.page_count == 2
    finally:
        output_document.close()


def test_missing_source_pdf_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.pdf"

    project = BookProject(
        inputs=[
            InputDocument(
                path=missing_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_export_structures(project)

    with pytest.raises(
        SignaturePdfExportError,
        match="does not exist",
    ):
        SignaturePdfExporter.export(
            project,
            stream,
            imposition,
            output_directory=tmp_path / "output",
        )


def test_changed_source_page_count_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 5)

    project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    stream, imposition = create_export_structures(project)

    with pytest.raises(
        SignaturePdfExportError,
        match="now contains 5 pages",
    ):
        SignaturePdfExporter.export(
            project,
            stream,
            imposition,
            output_directory=tmp_path / "output",
        )


def test_mismatched_stream_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "book.pdf"
    create_labelled_pdf(source_path, 8)

    four_page_project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=4,
            )
        ],
        signature_sheet_counts=[1],
    )

    eight_page_project = BookProject(
        inputs=[
            InputDocument(
                path=source_path,
                page_count=8,
            )
        ],
        signature_sheet_counts=[2],
    )

    four_page_plan = SignaturePlanner.create(
        four_page_project
    )
    four_page_imposition = BookletImposer.create(
        four_page_plan
    )

    eight_page_stream = LogicalPageStreamBuilder.create(
        eight_page_project
    )

    with pytest.raises(
        SignaturePdfExportError,
        match="logical stream contains 8 pages",
    ):
        SignaturePdfExporter.export(
            four_page_project,
            eight_page_stream,
            four_page_imposition,
            output_directory=tmp_path / "output",
        )