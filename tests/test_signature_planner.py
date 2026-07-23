"""Tests for explicit signature parsing and validation."""

from itertools import pairwise
from pathlib import Path

import pytest

from app.core import SignaturePlanError, SignaturePlanner
from app.models import (
    BlankPages,
    BookProject,
    InputDocument,
)


def make_project(
    page_count: int,
    *,
    blank_pages: int = 0,
) -> BookProject:
    """Create a project with one synthetic PDF."""

    inputs: list[InputDocument | BlankPages] = [
        InputDocument(
            path=Path("book.pdf"),
            page_count=page_count,
        )
    ]

    if blank_pages:
        inputs.append(BlankPages(quantity=blank_pages))

    return BookProject(inputs=inputs)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4-4-4-8-4", (4, 4, 4, 8, 4)),
        ("4, 4, 4, 8, 4", (4, 4, 4, 8, 4)),
        ("4 4 4 8 4", (4, 4, 4, 8, 4)),
        ("4 - 4, 8 4", (4, 4, 8, 4)),
    ],
)
def test_signature_sequence_accepts_supported_separators(
    value: str,
    expected: tuple[int, ...],
) -> None:
    assert SignaturePlanner.parse_signature_sequence(value) == expected


def test_signature_sequence_rejects_empty_value() -> None:
    with pytest.raises(
        SignaturePlanError,
        match="at least one",
    ):
        SignaturePlanner.parse_signature_sequence("")


def test_signature_sequence_rejects_invalid_characters() -> None:
    with pytest.raises(
        SignaturePlanError,
        match="whole numbers",
    ):
        SignaturePlanner.parse_signature_sequence("4/4/4")


def test_signature_sequence_rejects_zero_sheet_signature() -> None:
    with pytest.raises(
        SignaturePlanError,
        match="at least one sheet",
    ):
        SignaturePlanner.parse_signature_sequence("4-0-4")


def test_signature_sequence_has_standard_format() -> None:
    assert SignaturePlanner.format_signature_sequence((4, 4, 8, 4)) == "4-4-8-4"


def test_project_requires_at_least_one_pdf() -> None:
    project = BookProject(
        inputs=[BlankPages(quantity=4)],
        signature_sheet_counts=[1],
    )

    with pytest.raises(
        SignaturePlanError,
        match="at least one PDF",
    ):
        SignaturePlanner.create(project)


def test_input_page_count_must_be_divisible_by_four() -> None:
    project = make_project(101)
    project.signature_sheet_counts = [26]

    with pytest.raises(SignaturePlanError) as error:
        SignaturePlanner.create(project)

    assert error.value.blank_pages_required == 3
    assert "Add 3 blank pages" in str(error.value)


def test_inserted_blanks_can_make_input_divisible_by_four() -> None:
    project = make_project(101, blank_pages=3)
    project.signature_sheet_counts = [26]

    plan = SignaturePlanner.create(project)

    assert plan.total_page_count == 104
    assert plan.blank_page_count == 3


def test_signature_definition_is_required() -> None:
    project = make_project(100)

    with pytest.raises(
        SignaturePlanError,
        match="at least one signature",
    ):
        SignaturePlanner.create(project)


def test_plan_rejects_insufficient_signature_capacity() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 4, 4, 4, 4]

    with pytest.raises(SignaturePlanError) as error:
        SignaturePlanner.create(project)

    assert error.value.missing_pages == 16
    assert error.value.missing_sheets == 4
    assert "4 additional sheets" in str(error.value)


def test_plan_rejects_excess_signature_capacity() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 8, 4, 4, 8]

    with pytest.raises(SignaturePlanError) as error:
        SignaturePlanner.create(project)

    assert error.value.excess_pages == 16
    assert error.value.excess_sheets == 4
    assert "4 sheets too many" in str(error.value)


def test_valid_explicit_signature_plan_is_created() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 8, 4, 4, 4]

    plan = SignaturePlanner.create(project)

    assert plan.signature_count == 7
    assert plan.total_sheet_count == 32
    assert plan.total_page_count == 128
    assert plan.total_signature_page_capacity == 128


def test_signature_sizes_are_preserved_exactly() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 8, 4, 4, 4]

    plan = SignaturePlanner.create(project)

    assert [signature.sheet_count for signature in plan.signatures] == [4, 4, 4, 8, 4, 4, 4]


def test_signature_page_ranges_are_contiguous() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 8, 4, 4, 4]

    plan = SignaturePlanner.create(project)

    assert plan.signatures[0].start_page_index == 0
    assert plan.signatures[0].end_page_index == 15

    for previous, current in pairwise(plan.signatures):
        assert current.start_page_index == previous.end_page_index + 1

    assert plan.signatures[-1].end_page_index == 127


def test_large_signature_has_correct_page_range() -> None:
    project = make_project(128)
    project.signature_sheet_counts = [4, 4, 4, 8, 4, 4, 4]

    plan = SignaturePlanner.create(project)
    large_signature = plan.signatures[3]

    assert large_signature.number == 4
    assert large_signature.sheet_count == 8
    assert large_signature.page_count == 32
    assert large_signature.start_page_index == 48
    assert large_signature.end_page_index == 79


def test_sheet_counts_can_be_passed_directly_to_create() -> None:
    project = make_project(32)

    plan = SignaturePlanner.create(
        project,
        sheet_counts=(2, 2, 4),
    )

    assert plan.signature_count == 3
    assert plan.total_sheet_count == 8
