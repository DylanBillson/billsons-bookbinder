"""Tests for booklet page imposition."""

from itertools import chain
from pathlib import Path

import pytest

from app.core import (
    BookletImposer,
    BookletImpositionError,
    SignaturePlanner,
)
from app.models import (
    BookProject,
    InputDocument,
    PlannedSignature,
    SheetSide,
    SignaturePlan,
)


def make_project(
    page_count: int,
    signature_sheet_counts: list[int],
) -> BookProject:
    """Create a synthetic project with an explicit signature definition."""

    return BookProject(
        inputs=[
            InputDocument(
                path=Path("book.pdf"),
                page_count=page_count,
            )
        ],
        signature_sheet_counts=signature_sheet_counts,
    )


def test_one_sheet_signature_has_correct_imposition() -> None:
    project = make_project(4, [1])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)
    sheet = imposition.signatures[0].sheets[0]

    assert sheet.front.page_numbers == (4, 1)
    assert sheet.back.page_numbers == (2, 3)


def test_four_sheet_signature_has_standard_page_pairs() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[0]

    assert [sheet.front.page_numbers for sheet in signature.sheets] == [
        (16, 1),
        (14, 3),
        (12, 5),
        (10, 7),
    ]

    assert [sheet.back.page_numbers for sheet in signature.sheets] == [
        (2, 15),
        (4, 13),
        (6, 11),
        (8, 9),
    ]


def test_sheet_sides_are_labelled_correctly() -> None:
    project = make_project(4, [1])
    plan = SignaturePlanner.create(project)

    sheet = BookletImposer.create(plan).signatures[0].sheets[0]

    assert sheet.front.side is SheetSide.FRONT
    assert sheet.back.side is SheetSide.BACK


def test_sheet_numbers_begin_at_one() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[0]

    assert [sheet.number for sheet in signature.sheets] == [1, 2, 3, 4]


def test_multiple_signatures_use_their_own_page_ranges() -> None:
    project = make_project(32, [4, 4])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)
    first_signature = imposition.signatures[0]
    second_signature = imposition.signatures[1]

    assert first_signature.sheets[0].front.page_numbers == (16, 1)
    assert first_signature.sheets[0].back.page_numbers == (2, 15)

    assert second_signature.sheets[0].front.page_numbers == (32, 17)
    assert second_signature.sheets[0].back.page_numbers == (18, 31)


def test_mixed_signature_sizes_are_imposed_independently() -> None:
    project = make_project(32, [2, 4, 2])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)

    assert [signature.sheet_count for signature in imposition.signatures] == [2, 4, 2]

    assert imposition.signatures[0].sheets[0].front.page_numbers == (8, 1)
    assert imposition.signatures[1].sheets[0].front.page_numbers == (24, 9)
    assert imposition.signatures[2].sheets[0].front.page_numbers == (32, 25)


def test_large_middle_signature_has_correct_outer_sheet() -> None:
    project = make_project(128, [4, 4, 4, 8, 4, 4, 4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[3]

    assert signature.number == 4
    assert signature.sheet_count == 8
    assert signature.sheets[0].front.page_numbers == (80, 49)
    assert signature.sheets[0].back.page_numbers == (50, 79)


def test_large_middle_signature_has_correct_inner_sheet() -> None:
    project = make_project(128, [4, 4, 4, 8, 4, 4, 4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[3]
    inner_sheet = signature.sheets[-1]

    assert inner_sheet.front.page_numbers == (66, 63)
    assert inner_sheet.back.page_numbers == (64, 65)


def test_every_signature_page_is_used_exactly_once() -> None:
    project = make_project(32, [2, 4, 2])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)

    for planned, imposed in zip(
        plan.signatures,
        imposition.signatures,
        strict=True,
    ):
        expected = set(
            range(
                planned.start_page_index,
                planned.end_page_index + 1,
            )
        )

        assert set(imposed.page_indices) == expected
        assert len(imposed.page_indices) == len(expected)


def test_every_book_page_is_used_exactly_once() -> None:
    project = make_project(128, [4, 4, 4, 8, 4, 4, 4])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)

    assert set(imposition.page_indices) == set(range(128))
    assert len(imposition.page_indices) == 128


def test_imposition_totals_match_signature_plan() -> None:
    project = make_project(128, [4, 4, 4, 8, 4, 4, 4])
    plan = SignaturePlanner.create(project)

    imposition = BookletImposer.create(plan)

    assert imposition.signature_count == plan.signature_count
    assert imposition.total_sheet_count == plan.total_sheet_count
    assert imposition.total_page_count == plan.total_page_count


def test_front_and_back_together_contain_four_unique_pages() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[0]

    for sheet in signature.sheets:
        assert len(set(sheet.page_indices)) == 4


def test_outer_sheet_contains_first_and_last_pages() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    outer_sheet = BookletImposer.create(plan).signatures[0].sheets[0]

    assert 0 in outer_sheet.page_indices
    assert 15 in outer_sheet.page_indices


def test_inner_sheet_contains_centre_pages() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    inner_sheet = BookletImposer.create(plan).signatures[0].sheets[-1]

    assert set(inner_sheet.page_numbers) == {7, 8, 9, 10}


def test_all_front_pages_can_be_collected_in_print_order() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[0]

    front_page_numbers = list(
        chain.from_iterable(sheet.front.page_numbers for sheet in signature.sheets)
    )

    assert front_page_numbers == [
        16,
        1,
        14,
        3,
        12,
        5,
        10,
        7,
    ]


def test_all_back_pages_can_be_collected_in_print_order() -> None:
    project = make_project(16, [4])
    plan = SignaturePlanner.create(project)

    signature = BookletImposer.create(plan).signatures[0]

    back_page_numbers = list(
        chain.from_iterable(sheet.back.page_numbers for sheet in signature.sheets)
    )

    assert back_page_numbers == [
        2,
        15,
        4,
        13,
        6,
        11,
        8,
        9,
    ]


def test_empty_signature_plan_is_rejected() -> None:
    plan = SignaturePlan(
        source_pdf_page_count=0,
        blank_page_count=0,
        total_page_count=0,
        signatures=(),
    )

    with pytest.raises(
        BookletImpositionError,
        match="does not contain any signatures",
    ):
        BookletImposer.create(plan)


def test_signature_with_mismatched_sheet_and_page_count_is_rejected() -> None:
    signature = PlannedSignature(
        number=1,
        sheet_count=4,
        page_count=12,
        start_page_index=0,
        end_page_index=11,
    )

    with pytest.raises(
        BookletImpositionError,
        match="4 sheets require 16 pages",
    ):
        BookletImposer.impose_signature(signature)


def test_signature_with_invalid_page_range_is_rejected() -> None:
    signature = PlannedSignature(
        number=1,
        sheet_count=2,
        page_count=8,
        start_page_index=0,
        end_page_index=10,
    )

    with pytest.raises(
        BookletImpositionError,
        match="invalid page range",
    ):
        BookletImposer.impose_signature(signature)
