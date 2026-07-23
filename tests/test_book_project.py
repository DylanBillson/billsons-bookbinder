"""Tests for the central book project model."""

from pathlib import Path

import pytest

from app.models import (
    BlankPages,
    BookProject,
    InputDocument,
)


def make_document(
    filename: str,
    page_count: int,
) -> InputDocument:
    """Create a synthetic PDF input."""

    return InputDocument(
        path=Path(filename),
        page_count=page_count,
    )


def test_pdf_page_count_combines_all_documents() -> None:
    project = BookProject(
        inputs=[
            make_document("part-one.pdf", 20),
            BlankPages(quantity=4),
            make_document("part-two.pdf", 35),
        ]
    )

    assert project.source_pdf_page_count == 55


def test_blank_page_count_combines_all_blank_blocks() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 100),
            BlankPages(quantity=2),
            BlankPages(quantity=6),
        ]
    )

    assert project.blank_page_count == 8


def test_total_page_count_preserves_all_input_types() -> None:
    project = BookProject(
        inputs=[
            BlankPages(quantity=4),
            make_document("book.pdf", 100),
            BlankPages(quantity=8),
        ]
    )

    assert project.total_page_count == 112


def test_first_document_sets_default_book_name() -> None:
    project = BookProject()

    added = project.add_document(make_document("The Secret Garden.pdf", 120))

    assert added is True
    assert project.name == "the-secret-garden"


def test_blank_pages_before_first_pdf_do_not_prevent_naming() -> None:
    project = BookProject()
    project.add_blank_pages(4)
    project.add_document(make_document("The Secret Garden.pdf", 120))

    assert project.name == "the-secret-garden"


def test_duplicate_document_is_not_added() -> None:
    project = BookProject()
    document = make_document("book.pdf", 100)

    assert project.add_document(document) is True
    assert project.add_document(document) is False
    assert len(project.inputs) == 1


def test_blank_pages_can_be_inserted_between_documents() -> None:
    project = BookProject(
        inputs=[
            make_document("one.pdf", 10),
            make_document("two.pdf", 20),
        ]
    )

    project.add_blank_pages(6, index=1)

    assert isinstance(project.inputs[1], BlankPages)
    assert project.inputs[1].quantity == 6


def test_blank_page_quantity_can_be_edited() -> None:
    project = BookProject(
        inputs=[
            make_document("book.pdf", 100),
            BlankPages(quantity=2),
        ]
    )

    project.edit_blank_pages(1, 6)

    blank_pages = project.inputs[1]
    assert isinstance(blank_pages, BlankPages)
    assert blank_pages.quantity == 6


def test_editing_pdf_as_blank_pages_is_rejected() -> None:
    project = BookProject(inputs=[make_document("book.pdf", 100)])

    with pytest.raises(TypeError):
        project.edit_blank_pages(0, 4)


def test_zero_blank_pages_are_rejected() -> None:
    project = BookProject()

    with pytest.raises(ValueError):
        project.add_blank_pages(0)


def test_inputs_can_be_reordered() -> None:
    project = BookProject(
        inputs=[
            make_document("one.pdf", 10),
            BlankPages(quantity=4),
            make_document("two.pdf", 20),
        ]
    )

    project.move_input(2, 0)

    assert isinstance(project.inputs[0], InputDocument)
    assert project.inputs[0].filename == "two.pdf"
    assert project.name == "two"


def test_removing_final_document_restores_untitled_name() -> None:
    project = BookProject()
    project.add_document(make_document("book.pdf", 100))
    project.add_blank_pages(4)

    project.remove_input(0)

    assert project.name == "untitled-book"
    assert project.blank_page_count == 4


def test_signature_capacity_uses_four_pages_per_sheet() -> None:
    project = BookProject(signature_sheet_counts=[4, 4, 8])

    assert project.signature_count == 3
    assert project.signature_sheet_count == 16
    assert project.signature_page_capacity == 64
