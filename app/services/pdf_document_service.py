"""Services for inspecting input PDF documents."""

from pathlib import Path

import fitz

from app.models import InputDocument


class PdfDocumentError(Exception):
    """Raised when an input PDF cannot be inspected."""


class PdfDocumentService:
    """Read metadata from PDF documents selected by the user."""

    @staticmethod
    def inspect(path: Path) -> InputDocument:
        """Inspect a PDF and return its document metadata."""

        resolved_path = path.expanduser().resolve()

        if not resolved_path.exists():
            raise PdfDocumentError(f"The file does not exist:\n{resolved_path}")

        if not resolved_path.is_file():
            raise PdfDocumentError(f"The selected path is not a file:\n{resolved_path}")

        if resolved_path.suffix.lower() != ".pdf":
            raise PdfDocumentError(f"The selected file is not a PDF:\n{resolved_path}")

        try:
            with fitz.open(resolved_path) as pdf:
                if pdf.needs_pass:
                    raise PdfDocumentError(f"The PDF is password protected:\n{resolved_path.name}")

                if pdf.page_count < 1:
                    raise PdfDocumentError(
                        f"The PDF does not contain any pages:\n{resolved_path.name}"
                    )

                return InputDocument(
                    path=resolved_path,
                    page_count=pdf.page_count,
                )

        except PdfDocumentError:
            raise
        except (fitz.FileDataError, RuntimeError, ValueError) as exc:
            raise PdfDocumentError(
                f"The PDF could not be opened:\n{resolved_path.name}\n\n{exc}"
            ) from exc
