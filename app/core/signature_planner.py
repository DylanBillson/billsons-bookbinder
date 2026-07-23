"""Parse and validate explicit signature definitions."""

import re

from app.models import (
    BookProject,
    PlannedSignature,
    SignaturePlan,
)


class SignaturePlanError(ValueError):
    """Raised when a signature definition or project is invalid."""

    def __init__(
        self,
        message: str,
        *,
        missing_pages: int = 0,
        excess_pages: int = 0,
        blank_pages_required: int = 0,
    ) -> None:
        super().__init__(message)
        self.missing_pages = missing_pages
        self.excess_pages = excess_pages
        self.blank_pages_required = blank_pages_required

    @property
    def missing_sheets(self) -> int:
        """Return the number of additional sheets required."""

        return self.missing_pages // 4

    @property
    def excess_sheets(self) -> int:
        """Return the number of sheets by which the plan is too large."""

        return self.excess_pages // 4


class SignaturePlanner:
    """Parse and validate user-defined signature sheet counts."""

    _VALID_CHARACTERS = re.compile(r"^[\d\s,-]+$")
    _SEPARATORS = re.compile(r"[\s,-]+")

    @classmethod
    def parse_signature_sequence(cls, value: str) -> tuple[int, ...]:
        """Parse a signature definition into sheet counts."""

        stripped_value = value.strip()

        if not stripped_value:
            raise SignaturePlanError("Enter at least one signature size.")

        if cls._VALID_CHARACTERS.fullmatch(stripped_value) is None:
            raise SignaturePlanError(
                "Signature sizes may contain only whole numbers, spaces, commas and hyphens."
            )

        parts = [part for part in cls._SEPARATORS.split(stripped_value) if part]

        if not parts:
            raise SignaturePlanError("Enter at least one signature size.")

        sheet_counts = tuple(int(part) for part in parts)

        if any(sheet_count < 1 for sheet_count in sheet_counts):
            raise SignaturePlanError("Every signature must contain at least one sheet.")

        return sheet_counts

    @staticmethod
    def format_signature_sequence(
        sheet_counts: list[int] | tuple[int, ...],
    ) -> str:
        """Format sheet counts using the standard hyphen notation."""

        return "-".join(str(sheet_count) for sheet_count in sheet_counts)

    @staticmethod
    def create(
        project: BookProject,
        *,
        sheet_counts: tuple[int, ...] | list[int] | None = None,
    ) -> SignaturePlan:
        """Create a validated plan from the explicit signature sizes."""

        if not project.documents:
            raise SignaturePlanError("Add at least one PDF before creating a signature plan.")

        if project.total_page_count < 1:
            raise SignaturePlanError("The book does not contain any pages.")

        page_remainder = project.total_page_count % 4

        if page_remainder:
            blank_pages_required = 4 - page_remainder

            raise SignaturePlanError(
                (
                    f"The input contains {project.total_page_count} pages. "
                    f"Add {blank_pages_required} blank "
                    f"{'page' if blank_pages_required == 1 else 'pages'} "
                    "so the total is divisible by four."
                ),
                blank_pages_required=blank_pages_required,
            )

        selected_sheet_counts = tuple(
            project.signature_sheet_counts if sheet_counts is None else sheet_counts
        )

        if not selected_sheet_counts:
            raise SignaturePlanError("Enter at least one signature size.")

        if any(sheet_count < 1 for sheet_count in selected_sheet_counts):
            raise SignaturePlanError("Every signature must contain at least one sheet.")

        signature_page_capacity = sum(selected_sheet_counts) * 4
        difference = project.total_page_count - signature_page_capacity

        if difference > 0:
            sheet_word = "sheet" if difference == 4 else "sheets"

            raise SignaturePlanError(
                (
                    f"The signature plan covers "
                    f"{signature_page_capacity} pages, but the input "
                    f"contains {project.total_page_count} pages. "
                    f"The plan needs {difference // 4} additional "
                    f"{sheet_word}."
                ),
                missing_pages=difference,
            )

        if difference < 0:
            excess_pages = abs(difference)
            sheet_word = "sheet" if excess_pages == 4 else "sheets"

            raise SignaturePlanError(
                (
                    f"The signature plan covers "
                    f"{signature_page_capacity} pages, but the input "
                    f"contains {project.total_page_count} pages. "
                    f"The plan contains {excess_pages // 4} "
                    f"{sheet_word} too many."
                ),
                excess_pages=excess_pages,
            )

        signatures: list[PlannedSignature] = []
        next_page_index = 0

        for number, sheet_count in enumerate(
            selected_sheet_counts,
            start=1,
        ):
            page_count = sheet_count * 4
            end_page_index = next_page_index + page_count - 1

            signatures.append(
                PlannedSignature(
                    number=number,
                    sheet_count=sheet_count,
                    page_count=page_count,
                    start_page_index=next_page_index,
                    end_page_index=end_page_index,
                )
            )

            next_page_index = end_page_index + 1

        return SignaturePlan(
            source_pdf_page_count=project.source_pdf_page_count,
            blank_page_count=project.blank_page_count,
            total_page_count=project.total_page_count,
            signatures=tuple(signatures),
        )
