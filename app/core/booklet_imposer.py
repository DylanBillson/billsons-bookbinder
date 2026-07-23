"""Calculate booklet page placement for validated signatures."""

from app.models import (
    BookImposition,
    ImposedSheet,
    ImposedSide,
    ImposedSignature,
    PlannedSignature,
    SheetSide,
    SignaturePlan,
)


class BookletImpositionError(ValueError):
    """Raised when a signature cannot be imposed safely."""


class BookletImposer:
    """Convert validated signatures into printable sheet pairs."""

    @classmethod
    def create(cls, plan: SignaturePlan) -> BookImposition:
        """Create the complete booklet imposition for a signature plan."""

        if not plan.signatures:
            raise BookletImpositionError("The signature plan does not contain any signatures.")

        imposed_signatures = tuple(cls.impose_signature(signature) for signature in plan.signatures)

        imposition = BookImposition(signatures=imposed_signatures)
        cls._validate_complete_imposition(plan, imposition)

        return imposition

    @classmethod
    def impose_signature(
        cls,
        signature: PlannedSignature,
    ) -> ImposedSignature:
        """Impose one signature into front and back sheet pairs."""

        cls._validate_signature(signature)

        sheets: list[ImposedSheet] = []

        for sheet_offset in range(signature.sheet_count):
            front_left = signature.end_page_index - (sheet_offset * 2)
            front_right = signature.start_page_index + (sheet_offset * 2)

            back_left = front_right + 1
            back_right = front_left - 1

            sheets.append(
                ImposedSheet(
                    number=sheet_offset + 1,
                    front=ImposedSide(
                        side=SheetSide.FRONT,
                        left_page_index=front_left,
                        right_page_index=front_right,
                    ),
                    back=ImposedSide(
                        side=SheetSide.BACK,
                        left_page_index=back_left,
                        right_page_index=back_right,
                    ),
                )
            )

        imposed_signature = ImposedSignature(
            number=signature.number,
            start_page_index=signature.start_page_index,
            end_page_index=signature.end_page_index,
            sheets=tuple(sheets),
        )

        cls._validate_imposed_signature(
            signature,
            imposed_signature,
        )

        return imposed_signature

    @staticmethod
    def _validate_signature(signature: PlannedSignature) -> None:
        """Validate the source signature before imposing it."""

        if signature.number < 1:
            raise BookletImpositionError("Signature numbers must begin at 1.")

        if signature.sheet_count < 1:
            raise BookletImpositionError(
                f"Signature {signature.number} must contain at least one sheet."
            )

        if signature.page_count != signature.sheet_count * 4:
            raise BookletImpositionError(
                
                    f"Signature {signature.number} contains "
                    f"{signature.page_count} pages but "
                    f"{signature.sheet_count} sheets require "
                    f"{signature.sheet_count * 4} pages."
                
            )

        if signature.start_page_index < 0:
            raise BookletImpositionError("Signature page indices cannot be negative.")

        expected_end_index = signature.start_page_index + signature.page_count - 1

        if signature.end_page_index != expected_end_index:
            raise BookletImpositionError(
                
                    f"Signature {signature.number} has an invalid page range. "
                    f"Expected its final page index to be "
                    f"{expected_end_index}, not "
                    f"{signature.end_page_index}."
                
            )

    @staticmethod
    def _validate_imposed_signature(
        source: PlannedSignature,
        imposed: ImposedSignature,
    ) -> None:
        """Ensure a signature uses every expected page exactly once."""

        expected_indices = set(
            range(
                source.start_page_index,
                source.end_page_index + 1,
            )
        )
        imposed_indices = imposed.page_indices
        actual_indices = set(imposed_indices)

        if len(imposed_indices) != len(actual_indices):
            raise BookletImpositionError(
                f"Signature {source.number} places at least one page more than once."
            )

        if actual_indices != expected_indices:
            missing = sorted(expected_indices - actual_indices)
            unexpected = sorted(actual_indices - expected_indices)

            raise BookletImpositionError(
                
                    f"Signature {source.number} produced an invalid "
                    f"page arrangement. Missing indices: {missing}; "
                    f"unexpected indices: {unexpected}."
                
            )

    @staticmethod
    def _validate_complete_imposition(
        plan: SignaturePlan,
        imposition: BookImposition,
    ) -> None:
        """Ensure every book page appears exactly once."""

        expected_indices = set(range(plan.total_page_count))
        imposed_indices = imposition.page_indices
        actual_indices = set(imposed_indices)

        if len(imposed_indices) != len(actual_indices):
            raise BookletImpositionError("The complete imposition contains duplicate pages.")

        if actual_indices != expected_indices:
            missing = sorted(expected_indices - actual_indices)
            unexpected = sorted(actual_indices - expected_indices)

            raise BookletImpositionError(
                
                    "The complete imposition does not match the book. "
                    f"Missing indices: {missing}; "
                    f"unexpected indices: {unexpected}."
                
            )
