"""Calculate the physical signature structure for a book."""

from dataclasses import dataclass

from app.models import (
    BookProject,
    IncompleteSignatureMode,
    PlannedSignature,
    SignatureKind,
    SignaturePlan,
    SmallerSignaturePosition,
)


class SignaturePlanError(ValueError):
    """Raised when the current project cannot form a valid signature plan."""

    def __init__(
        self,
        message: str,
        *,
        additional_blank_pages_required: int = 0,
    ) -> None:
        super().__init__(message)
        self.additional_blank_pages_required = additional_blank_pages_required


@dataclass(frozen=True, slots=True)
class SignatureRequirements:
    """Validation information for the project's current page count."""

    current_page_count: int
    pages_per_signature: int
    pages_to_next_sheet: int
    pages_to_next_full_signature: int

    @property
    def is_sheet_aligned(self) -> bool:
        """Return whether the current page count fills whole sheets."""

        return self.pages_to_next_sheet == 0

    @property
    def is_full_signature_aligned(self) -> bool:
        """Return whether all normal signatures would be full."""

        return self.pages_to_next_full_signature == 0


class SignaturePlanner:
    """Create signature plans from a book project's current settings."""

    @staticmethod
    def requirements(project: BookProject) -> SignatureRequirements:
        """Calculate blank-page requirements without creating a plan."""

        SignaturePlanner._validate_basic_settings(project)

        page_count = project.total_page_count
        pages_per_signature = project.pages_per_signature

        pages_to_next_sheet = (-page_count) % 4
        pages_to_next_full_signature = (-page_count) % pages_per_signature

        return SignatureRequirements(
            current_page_count=page_count,
            pages_per_signature=pages_per_signature,
            pages_to_next_sheet=pages_to_next_sheet,
            pages_to_next_full_signature=pages_to_next_full_signature,
        )

    @staticmethod
    def create(project: BookProject) -> SignaturePlan:
        """Create a complete signature plan for the project."""

        SignaturePlanner._validate_basic_settings(project)

        if project.source_page_count < 1:
            raise SignaturePlanError("At least one source PDF page is required.")

        requirements = SignaturePlanner.requirements(project)

        if not requirements.is_sheet_aligned:
            required = requirements.pages_to_next_sheet

            raise SignaturePlanError(
                (
                    "The current page total does not fill complete sheets. "
                    f"Add {required} more blank page"
                    f"{'' if required == 1 else 's'}."
                ),
                additional_blank_pages_required=required,
            )

        if project.signature_settings.handling is IncompleteSignatureMode.ADD_BLANKS:
            return SignaturePlanner._create_fully_padded_plan(project)

        return SignaturePlanner._create_smaller_signature_plan(project)

    @staticmethod
    def _create_fully_padded_plan(project: BookProject) -> SignaturePlan:
        """Create a plan in which every signature is full size."""

        page_count = project.total_page_count
        pages_per_signature = project.pages_per_signature
        remainder = page_count % pages_per_signature

        if remainder:
            required = pages_per_signature - remainder

            raise SignaturePlanError(
                (
                    "The current page total does not fill complete "
                    f"{project.print_settings.sheets_per_signature}-sheet "
                    f"signatures. Add {required} more blank page"
                    f"{'' if required == 1 else 's'}."
                ),
                additional_blank_pages_required=required,
            )

        signature_count = page_count // pages_per_signature
        signatures = SignaturePlanner._build_full_signatures(
            signature_count=signature_count,
            sheets_per_signature=(project.print_settings.sheets_per_signature),
            pages_per_signature=pages_per_signature,
        )

        return SignaturePlanner._build_plan(project, signatures)

    @staticmethod
    def _create_smaller_signature_plan(
        project: BookProject,
    ) -> SignaturePlan:
        """Create a plan that permits one smaller signature."""

        total_pages = project.total_page_count
        normal_pages = project.pages_per_signature
        normal_sheets = project.print_settings.sheets_per_signature

        full_signature_count, remainder_pages = divmod(
            total_pages,
            normal_pages,
        )

        full_signatures = list(
            SignaturePlanner._build_full_signatures(
                signature_count=full_signature_count,
                sheets_per_signature=normal_sheets,
                pages_per_signature=normal_pages,
            )
        )

        if remainder_pages == 0:
            return SignaturePlanner._build_plan(
                project,
                tuple(full_signatures),
            )

        smaller_signature = PlannedSignature(
            number=0,
            kind=SignatureKind.SMALLER,
            sheet_count=remainder_pages // 4,
            page_count=remainder_pages,
            start_page_index=0,
            end_page_index=0,
        )

        insertion_index = SignaturePlanner._smaller_signature_insertion_index(
            full_signature_count=full_signature_count,
            position=(project.signature_settings.smaller_signature_position),
        )

        full_signatures.insert(insertion_index, smaller_signature)

        renumbered = SignaturePlanner._renumber_and_reindex(full_signatures)

        return SignaturePlanner._build_plan(project, renumbered)

    @staticmethod
    def _build_full_signatures(
        *,
        signature_count: int,
        sheets_per_signature: int,
        pages_per_signature: int,
    ) -> tuple[PlannedSignature, ...]:
        """Build an initial sequence of full signatures."""

        signatures: list[PlannedSignature] = []

        for index in range(signature_count):
            start_page_index = index * pages_per_signature
            end_page_index = start_page_index + pages_per_signature - 1

            signatures.append(
                PlannedSignature(
                    number=index + 1,
                    kind=SignatureKind.FULL,
                    sheet_count=sheets_per_signature,
                    page_count=pages_per_signature,
                    start_page_index=start_page_index,
                    end_page_index=end_page_index,
                )
            )

        return tuple(signatures)

    @staticmethod
    def _smaller_signature_insertion_index(
        *,
        full_signature_count: int,
        position: SmallerSignaturePosition,
    ) -> int:
        """Determine where the smaller signature belongs."""

        if position is SmallerSignaturePosition.BEGINNING:
            return 0

        if position is SmallerSignaturePosition.END:
            return full_signature_count

        return (full_signature_count + 1) // 2

    @staticmethod
    def _renumber_and_reindex(
        signatures: list[PlannedSignature],
    ) -> tuple[PlannedSignature, ...]:
        """Assign final sequence numbers and contiguous page ranges."""

        result: list[PlannedSignature] = []
        next_page_index = 0

        for number, signature in enumerate(signatures, start=1):
            end_page_index = next_page_index + signature.page_count - 1

            result.append(
                PlannedSignature(
                    number=number,
                    kind=signature.kind,
                    sheet_count=signature.sheet_count,
                    page_count=signature.page_count,
                    start_page_index=next_page_index,
                    end_page_index=end_page_index,
                )
            )

            next_page_index = end_page_index + 1

        return tuple(result)

    @staticmethod
    def _build_plan(
        project: BookProject,
        signatures: tuple[PlannedSignature, ...],
    ) -> SignaturePlan:
        """Build the final immutable signature plan."""

        return SignaturePlan(
            source_page_count=project.source_page_count,
            blank_pages_start=(project.signature_settings.blank_pages_start),
            blank_pages_end=project.signature_settings.blank_pages_end,
            total_page_count=project.total_page_count,
            normal_sheets_per_signature=(project.print_settings.sheets_per_signature),
            normal_pages_per_signature=project.pages_per_signature,
            signatures=signatures,
        )

    @staticmethod
    def _validate_basic_settings(project: BookProject) -> None:
        """Validate settings required by every planning mode."""

        if project.print_settings.sheets_per_signature < 1:
            raise SignaturePlanError("Sheets per signature must be at least 1.")

        if project.signature_settings.blank_pages_start < 0:
            raise SignaturePlanError("Blank pages at the beginning cannot be negative.")

        if project.signature_settings.blank_pages_end < 0:
            raise SignaturePlanError("Blank pages at the end cannot be negative.")
