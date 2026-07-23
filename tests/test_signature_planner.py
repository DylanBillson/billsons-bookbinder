"""Tests for signature planning."""

from itertools import pairwise
from pathlib import Path

import pytest

from app.core import SignaturePlanError, SignaturePlanner
from app.models import (
    BookProject,
    IncompleteSignatureMode,
    InputDocument,
    SignatureKind,
    SmallerSignaturePosition,
)


def make_project(
    page_count: int,
    *,
    sheets_per_signature: int = 4,
) -> BookProject:
    """Create a project with one synthetic input document."""

    project = BookProject(
        documents=[
            InputDocument(
                path=Path("book.pdf"),
                page_count=page_count,
            )
        ]
    )
    project.print_settings.sheets_per_signature = sheets_per_signature
    return project


def test_requirements_reports_pages_needed_for_complete_sheet() -> None:
    project = make_project(101)

    requirements = SignaturePlanner.requirements(project)

    assert requirements.pages_to_next_sheet == 3


def test_requirements_reports_pages_needed_for_full_signature() -> None:
    project = make_project(100)

    requirements = SignaturePlanner.requirements(project)

    assert requirements.pages_to_next_full_signature == 12


def test_add_blanks_mode_creates_only_full_signatures() -> None:
    project = make_project(112)
    project.signature_settings.handling = IncompleteSignatureMode.ADD_BLANKS

    plan = SignaturePlanner.create(project)

    assert plan.signature_count == 7
    assert plan.full_signature_count == 7
    assert plan.smaller_signature is None
    assert plan.total_sheet_count == 28
    assert all(signature.kind is SignatureKind.FULL for signature in plan.signatures)


def test_add_blanks_mode_rejects_incomplete_full_signature() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.ADD_BLANKS

    with pytest.raises(SignaturePlanError) as error:
        SignaturePlanner.create(project)

    assert error.value.additional_blank_pages_required == 12


def test_add_blanks_mode_accepts_blanks_split_between_start_and_end() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.ADD_BLANKS
    project.signature_settings.blank_pages_start = 4
    project.signature_settings.blank_pages_end = 8

    plan = SignaturePlanner.create(project)

    assert plan.total_page_count == 112
    assert plan.blank_pages_start == 4
    assert plan.blank_pages_end == 8
    assert plan.signature_count == 7


def test_user_can_add_more_than_minimum_when_total_remains_valid() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.ADD_BLANKS
    project.signature_settings.blank_pages_start = 8
    project.signature_settings.blank_pages_end = 20

    plan = SignaturePlanner.create(project)

    assert plan.total_page_count == 128
    assert plan.signature_count == 8


def test_smaller_signature_mode_creates_smaller_signature_at_end() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE
    project.signature_settings.smaller_signature_position = SmallerSignaturePosition.END

    plan = SignaturePlanner.create(project)

    assert plan.full_signature_count == 6
    assert plan.signature_count == 7
    assert plan.smaller_signature is not None
    assert plan.smaller_signature.sheet_count == 1
    assert plan.smaller_signature.page_count == 4
    assert plan.signatures[-1].is_smaller


def test_smaller_signature_can_be_placed_at_beginning() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE
    project.signature_settings.smaller_signature_position = SmallerSignaturePosition.BEGINNING

    plan = SignaturePlanner.create(project)

    assert plan.signatures[0].is_smaller
    assert plan.signatures[0].page_count == 4
    assert plan.signatures[1].start_page_index == 4


def test_smaller_signature_can_be_placed_in_middle() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE
    project.signature_settings.smaller_signature_position = SmallerSignaturePosition.MIDDLE

    plan = SignaturePlanner.create(project)

    assert [signature.page_count for signature in plan.signatures] == [
        16,
        16,
        16,
        4,
        16,
        16,
        16,
    ]


def test_smaller_signature_mode_still_requires_complete_sheets() -> None:
    project = make_project(102)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE

    with pytest.raises(SignaturePlanError) as error:
        SignaturePlanner.create(project)

    assert error.value.additional_blank_pages_required == 2


def test_smaller_mode_has_no_smaller_signature_when_division_is_exact() -> None:
    project = make_project(96)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE

    plan = SignaturePlanner.create(project)

    assert plan.signature_count == 6
    assert plan.full_signature_count == 6
    assert plan.smaller_signature is None


def test_signature_page_ranges_are_contiguous() -> None:
    project = make_project(100)
    project.signature_settings.handling = IncompleteSignatureMode.SMALLER_SIGNATURE
    project.signature_settings.smaller_signature_position = SmallerSignaturePosition.MIDDLE

    plan = SignaturePlanner.create(project)

    assert plan.signatures[0].start_page_index == 0
    assert plan.signatures[0].end_page_index == 15

    for previous, current in pairwise(plan.signatures):
        assert current.start_page_index == previous.end_page_index + 1

    assert plan.signatures[-1].end_page_index == 99


def test_empty_project_cannot_create_plan() -> None:
    project = BookProject()

    with pytest.raises(SignaturePlanError, match="At least one"):
        SignaturePlanner.create(project)


def test_zero_sheets_per_signature_is_rejected() -> None:
    project = make_project(100)
    project.print_settings.sheets_per_signature = 0

    with pytest.raises(
        SignaturePlanError,
        match="must be at least 1",
    ):
        SignaturePlanner.create(project)
