"""Tests for the central book project model."""

from pathlib import Path

from app.models import BookProject, InputDocument


def test_source_page_count_combines_all_documents() -> None:
    project = BookProject(
        documents=[
            InputDocument(Path("part-one.pdf"), 20),
            InputDocument(Path("part-two.pdf"), 35),
        ]
    )

    assert project.source_page_count == 55


def test_pages_per_signature_uses_four_pages_per_sheet() -> None:
    project = BookProject()
    project.print_settings.sheets_per_signature = 6

    assert project.pages_per_signature == 24


def test_first_document_sets_default_book_name() -> None:
    project = BookProject()

    added = project.add_document(InputDocument(Path("The Secret Garden.pdf"), 120))

    assert added is True
    assert project.name == "the-secret-garden"


def test_duplicate_document_is_not_added() -> None:
    project = BookProject()
    document = InputDocument(Path("book.pdf"), 100)

    assert project.add_document(document) is True
    assert project.add_document(document) is False
    assert len(project.documents) == 1


def test_document_can_be_reordered() -> None:
    project = BookProject(
        documents=[
            InputDocument(Path("one.pdf"), 10),
            InputDocument(Path("two.pdf"), 20),
            InputDocument(Path("three.pdf"), 30),
        ]
    )

    project.move_document(2, 0)

    assert [document.filename for document in project.documents] == [
        "three.pdf",
        "one.pdf",
        "two.pdf",
    ]


def test_removing_final_document_restores_untitled_name() -> None:
    project = BookProject()
    project.add_document(InputDocument(Path("book.pdf"), 100))

    project.remove_document(0)

    assert project.documents == []
    assert project.name == "untitled-book"
