"""Tests for the ordered logical page stream."""

from pathlib import Path

import pytest

from app.core import (
    LogicalPageStreamBuilder,
    LogicalPageStreamError,
)
from app.models import (
    BlankLogicalPage,
    BlankPages,
    BookProject,
    InputDocument,
    SourceLogicalPage,
)


def make_document(
    filename: str,
    page_count: int,
) -> InputDocument:
    """Create a synthetic input PDF."""

    return InputDocument(
        path=Path(filename),
        page_count=page_count,
    )


def test_single_pdf_expands_into_source_pages() -> None:
    project = BookProject(inputs=[make_document("book.pdf", 3)])

    stream = LogicalPageStreamBuilder.create(project)

    assert stream.page_count == 3
    assert stream.source_page_count == 3
    assert stream.blank_page_count == 0

    assert all(isinstance(page, SourceLogicalPage) for page in stream)


def test_source_pages_use_contiguous_book_indices() -> None:
    project = BookProject(inputs=[make_document("book.pdf", 3)])

    stream = LogicalPageStreamBuilder.create(project)

    assert [page.book_page_index for page in stream] == [0, 1, 2]


def test_source_pages_preserve_document_page_indices() -> None:
    project = BookProject(inputs=[make_document("book.pdf", 3)])

    stream = LogicalPageStreamBuilder.create(project)

    assert [page.document_page_index for page in stream if isinstance(page, SourceLogicalPage)] == [
        0,
        1,
        2,
    ]


def test_source_pages_expose_one_based_numbers() -> None:
    project = BookProject(inputs=[make_document("book.pdf", 3)])

    stream = LogicalPageStreamBuilder.create(project)
    final_page = stream[2]

    assert isinstance(final_page, SourceLogicalPage)
    assert final_page.book_page_number == 3
    assert final_page.document_page_number == 3


def test_blank_pages_before_pdf_appear_first() -> None:
    project = BookProject(
        inputs=[
            BlankPages(quantity=2),
            make_document("book.pdf", 3),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert isinstance(stream[0], BlankLogicalPage)
    assert isinstance(stream[1], BlankLogicalPage)
    assert isinstance(stream[2], SourceLogicalPage)

    first_source_page = stream[2]
    assert first_source_page.document_page_index == 0
    assert first_source_page.book_page_index == 2


def test_blank_pages_after_pdf_appear_last() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 2),
            BlankPages(quantity=2),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert isinstance(stream[0], SourceLogicalPage)
    assert isinstance(stream[1], SourceLogicalPage)
    assert isinstance(stream[2], BlankLogicalPage)
    assert isinstance(stream[3], BlankLogicalPage)


def test_blank_pages_can_appear_between_pdfs() -> None:
    project = BookProject(
        inputs=[
            make_document("front.pdf", 2),
            BlankPages(quantity=3),
            make_document("body.pdf", 2),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert [page.is_blank for page in stream] == [
        False,
        False,
        True,
        True,
        True,
        False,
        False,
    ]


def test_multiple_documents_restart_their_own_page_indices() -> None:
    project = BookProject(
        inputs=[
            make_document("one.pdf", 2),
            make_document("two.pdf", 3),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    source_pages = [page for page in stream if isinstance(page, SourceLogicalPage)]

    assert [page.document_page_index for page in source_pages] == [0, 1, 0, 1, 2]


def test_multiple_documents_preserve_their_paths() -> None:
    project = BookProject(
        inputs=[
            make_document("one.pdf", 1),
            make_document("two.pdf", 1),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    first_page = stream[0]
    second_page = stream[1]

    assert isinstance(first_page, SourceLogicalPage)
    assert isinstance(second_page, SourceLogicalPage)

    assert first_page.document_path == Path("one.pdf")
    assert second_page.document_path == Path("two.pdf")


def test_input_indices_identify_originating_entries() -> None:
    project = BookProject(
        inputs=[
            make_document("one.pdf", 2),
            BlankPages(quantity=2),
            make_document("two.pdf", 2),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert [page.input_index for page in stream] == [0, 0, 1, 1, 2, 2]


def test_blank_indices_restart_for_each_blank_block() -> None:
    project = BookProject(
        inputs=[
            BlankPages(quantity=2),
            make_document("book.pdf", 1),
            BlankPages(quantity=3),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    blank_pages = [page for page in stream if isinstance(page, BlankLogicalPage)]

    assert [page.blank_index for page in blank_pages] == [0, 1, 0, 1, 2]


def test_blank_pages_expose_one_based_block_numbers() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 1),
            BlankPages(quantity=3),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)
    final_page = stream[-1]

    assert isinstance(final_page, BlankLogicalPage)
    assert final_page.book_page_number == 4
    assert final_page.blank_number == 3


def test_stream_supports_length_iteration_and_indexing() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 2),
            BlankPages(quantity=1),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert len(stream) == 3
    assert list(stream) == list(stream.pages)
    assert stream[0] is stream.pages[0]
    assert stream[-1] is stream.pages[-1]


def test_37_page_example_resolves_expected_boundaries() -> None:
    project = BookProject(
        inputs=[
            BlankPages(quantity=1),
            make_document("book.pdf", 37),
            BlankPages(quantity=2),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert stream.page_count == 40
    assert stream.source_page_count == 37
    assert stream.blank_page_count == 3

    assert isinstance(stream[0], BlankLogicalPage)

    first_pdf_page = stream[1]
    assert isinstance(first_pdf_page, SourceLogicalPage)
    assert first_pdf_page.document_page_number == 1
    assert first_pdf_page.book_page_number == 2

    final_pdf_page = stream[37]
    assert isinstance(final_pdf_page, SourceLogicalPage)
    assert final_pdf_page.document_page_number == 37
    assert final_pdf_page.book_page_number == 38

    assert isinstance(stream[38], BlankLogicalPage)
    assert isinstance(stream[39], BlankLogicalPage)


def test_37_page_example_matches_signature_boundaries() -> None:
    project = BookProject(
        inputs=[
            BlankPages(quantity=1),
            make_document("book.pdf", 37),
            BlankPages(quantity=2),
        ]
    )

    stream = LogicalPageStreamBuilder.create(project)

    assert stream[0].book_page_number == 1
    assert stream[15].book_page_number == 16
    assert stream[16].book_page_number == 17
    assert stream[31].book_page_number == 32
    assert stream[32].book_page_number == 33
    assert stream[39].book_page_number == 40


def test_empty_project_is_rejected() -> None:
    project = BookProject()

    with pytest.raises(
        LogicalPageStreamError,
        match="does not contain any input",
    ):
        LogicalPageStreamBuilder.create(project)


def test_blank_only_project_is_rejected() -> None:
    project = BookProject(inputs=[BlankPages(quantity=4)])

    with pytest.raises(
        LogicalPageStreamError,
        match="at least one PDF",
    ):
        LogicalPageStreamBuilder.create(project)


def test_zero_page_pdf_is_rejected() -> None:
    project = BookProject(inputs=[make_document("empty.pdf", 0)])

    with pytest.raises(
        LogicalPageStreamError,
        match="at least one page",
    ):
        LogicalPageStreamBuilder.create(project)


def test_zero_quantity_blank_block_is_rejected() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 4),
            BlankPages(quantity=0),
        ]
    )

    with pytest.raises(
        LogicalPageStreamError,
        match="at least one page",
    ):
        LogicalPageStreamBuilder.create(project)
