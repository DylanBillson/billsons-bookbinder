"""Generate imposed signature PDF files."""

from contextlib import ExitStack
from pathlib import Path
import re

import pymupdf

from app.models import (
    BlankLogicalPage,
    BookImposition,
    BookProject,
    ExportedSignaturePdf,
    ImposedSide,
    LogicalPage,
    LogicalPageStream,
    PageFittingMode,
    PaperSize,
    PdfExportResult,
    SourceLogicalPage,
)


class SignaturePdfExportError(RuntimeError):
    """Raised when imposed PDF output cannot be generated."""


class SignaturePdfExporter:
    """Generate imposed signature PDF files."""

    _MM_TO_POINTS = 72.0 / 25.4

    _PAPER_SIZES_MM: dict[PaperSize, tuple[float, float]] = {
        PaperSize.A3: (297.0, 420.0),
        PaperSize.A4: (210.0, 297.0),
        PaperSize.A5: (148.0, 210.0),
    }

    @classmethod
    def export(
        cls,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        *,
        output_directory: Path | None = None,
        separate_duplex_outputs: bool = False,
        combine_signatures: bool = False,
    ) -> PdfExportResult:
        """Export the imposed signatures using the selected output mode."""

        cls._validate_inputs(project, stream, imposition)

        if combine_signatures and separate_duplex_outputs:
            raise SignaturePdfExportError(
                "Combined export cannot be used with separate A-side and "
                "B-side output."
            )

        selected_output_directory = (
            project.output_directory
            if output_directory is None
            else Path(output_directory)
        )

        selected_output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        book_slug = cls._filename_slug(project.name)

        with ExitStack() as stack:
            source_documents = cls._open_source_documents(
                project,
                stack=stack,
            )

            if combine_signatures:
                return cls._export_combined_signatures(
                    project=project,
                    stream=stream,
                    imposition=imposition,
                    source_documents=source_documents,
                    output_directory=selected_output_directory,
                    book_slug=book_slug,
                )

            exported_signatures = cls._export_individual_signatures(
                project=project,
                stream=stream,
                imposition=imposition,
                source_documents=source_documents,
                output_directory=selected_output_directory,
                book_slug=book_slug,
                separate_duplex_outputs=separate_duplex_outputs,
            )

        return PdfExportResult(
            output_directory=selected_output_directory,
            signatures=tuple(exported_signatures),
        )

    @classmethod
    def _export_individual_signatures(
        cls,
        *,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        source_documents: dict[Path, pymupdf.Document],
        output_directory: Path,
        book_slug: str,
        separate_duplex_outputs: bool,
    ) -> list[ExportedSignaturePdf]:
        """Export one or two files for each signature."""

        exported_signatures: list[ExportedSignaturePdf] = []

        for signature in imposition.signatures:
            if separate_duplex_outputs:
                a_path = (
                    output_directory
                    / f"{signature.number}a-signature-{book_slug}.pdf"
                )
                b_path = (
                    output_directory
                    / f"{signature.number}b-signature-{book_slug}.pdf"
                )

                cls._export_signature(
                    project=project,
                    stream=stream,
                    signature=signature,
                    source_documents=source_documents,
                    output_path=a_path,
                    include_front=True,
                    include_back=False,
                    title_suffix="Side A",
                )

                cls._export_signature(
                    project=project,
                    stream=stream,
                    signature=signature,
                    source_documents=source_documents,
                    output_path=b_path,
                    include_front=False,
                    include_back=True,
                    title_suffix="Side B",
                )

                output_paths = (a_path, b_path)
            else:
                output_path = (
                    output_directory
                    / f"{signature.number}-signature-{book_slug}.pdf"
                )

                cls._export_signature(
                    project=project,
                    stream=stream,
                    signature=signature,
                    source_documents=source_documents,
                    output_path=output_path,
                    include_front=True,
                    include_back=True,
                )

                output_paths = (output_path,)

            exported_signatures.append(
                ExportedSignaturePdf(
                    signature_number=signature.number,
                    sheet_count=signature.sheet_count,
                    output_page_count=signature.sheet_count * 2,
                    paths=output_paths,
                )
            )

        return exported_signatures

    @classmethod
    def _export_combined_signatures(
        cls,
        *,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        source_documents: dict[Path, pymupdf.Document],
        output_directory: Path,
        book_slug: str,
    ) -> PdfExportResult:
        """Export every signature into one duplex PDF.

        One blank physical separator sheet is inserted between neighbouring
        signatures. Because the document is duplex, each separator consists
        of two blank PDF pages.
        """

        output_path = output_directory / f"combined-signatures-{book_slug}.pdf"
        temporary_path = output_path.with_suffix(".pdf.tmp")

        cls._remove_temporary_file(temporary_path)

        output_document = pymupdf.open()

        try:
            sheet_width, sheet_height = cls._sheet_size_points(
                project.print_settings.paper_size
            )

            left_rect, right_rect = cls._page_destination_rects(
                project,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
            )

            signatures = tuple(imposition.signatures)

            for signature_index, signature in enumerate(signatures):
                cls._append_signature_pages(
                    output_document=output_document,
                    project=project,
                    stream=stream,
                    signature=signature,
                    source_documents=source_documents,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    left_rect=left_rect,
                    right_rect=right_rect,
                    include_front=True,
                    include_back=True,
                )

                is_last_signature = signature_index == len(signatures) - 1

                if not is_last_signature:
                    cls._append_blank_sheet(
                        output_document=output_document,
                        sheet_width=sheet_width,
                        sheet_height=sheet_height,
                    )

            output_document.set_metadata(
                {
                    "title": f"{project.name} - Combined Signatures",
                    "subject": (
                        "Booklet-imposed signatures with separator sheets"
                    ),
                    "creator": "Billson's Bookbinder",
                    "producer": "PyMuPDF",
                }
            )

            cls._save_document(
                output_document=output_document,
                temporary_path=temporary_path,
                output_path=output_path,
            )
        except SignaturePdfExportError:
            cls._remove_temporary_file(temporary_path)
            raise
        except Exception as exc:
            cls._remove_temporary_file(temporary_path)
            raise SignaturePdfExportError(
                f"Could not generate the combined signature PDF: {exc}"
            ) from exc
        finally:
            output_document.close()

        exported_signatures: list[ExportedSignaturePdf] = []
        signatures = tuple(imposition.signatures)

        for signature_index, signature in enumerate(signatures):
            has_separator_after = signature_index < len(signatures) - 1

            exported_signatures.append(
                ExportedSignaturePdf(
                    signature_number=signature.number,
                    sheet_count=(
                        signature.sheet_count
                        + (1 if has_separator_after else 0)
                    ),
                    output_page_count=(
                        signature.sheet_count * 2
                        + (2 if has_separator_after else 0)
                    ),
                    paths=(output_path,) if signature_index == 0 else (),
                )
            )

        return PdfExportResult(
            output_directory=output_directory,
            signatures=tuple(exported_signatures),
        )

    @classmethod
    def _export_signature(
        cls,
        *,
        project: BookProject,
        stream: LogicalPageStream,
        signature,
        source_documents: dict[Path, pymupdf.Document],
        output_path: Path,
        include_front: bool,
        include_back: bool,
        title_suffix: str | None = None,
    ) -> None:
        """Generate one imposed signature PDF."""

        if not include_front and not include_back:
            raise SignaturePdfExportError(
                "At least one sheet side must be included in the export."
            )

        temporary_path = output_path.with_suffix(".pdf.tmp")
        cls._remove_temporary_file(temporary_path)

        output_document = pymupdf.open()

        try:
            sheet_width, sheet_height = cls._sheet_size_points(
                project.print_settings.paper_size
            )

            left_rect, right_rect = cls._page_destination_rects(
                project,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
            )

            cls._append_signature_pages(
                output_document=output_document,
                project=project,
                stream=stream,
                signature=signature,
                source_documents=source_documents,
                sheet_width=sheet_width,
                sheet_height=sheet_height,
                left_rect=left_rect,
                right_rect=right_rect,
                include_front=include_front,
                include_back=include_back,
            )

            title = f"{project.name} - Signature {signature.number}"

            if title_suffix is not None:
                title = f"{title} - {title_suffix}"

            output_document.set_metadata(
                {
                    "title": title,
                    "subject": "Booklet-imposed signature",
                    "creator": "Billson's Bookbinder",
                    "producer": "PyMuPDF",
                }
            )

            cls._save_document(
                output_document=output_document,
                temporary_path=temporary_path,
                output_path=output_path,
            )
        except SignaturePdfExportError:
            cls._remove_temporary_file(temporary_path)
            raise
        except Exception as exc:
            cls._remove_temporary_file(temporary_path)
            raise SignaturePdfExportError(
                f"Could not generate signature {signature.number}: {exc}"
            ) from exc
        finally:
            output_document.close()

    @classmethod
    def _append_signature_pages(
        cls,
        *,
        output_document: pymupdf.Document,
        project: BookProject,
        stream: LogicalPageStream,
        signature,
        source_documents: dict[Path, pymupdf.Document],
        sheet_width: float,
        sheet_height: float,
        left_rect: pymupdf.Rect,
        right_rect: pymupdf.Rect,
        include_front: bool,
        include_back: bool,
    ) -> None:
        """Append the selected sides from one imposed signature."""

        for sheet in signature.sheets:
            if include_front:
                cls._append_imposed_side(
                    output_document=output_document,
                    side=sheet.front,
                    stream=stream,
                    source_documents=source_documents,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    left_rect=left_rect,
                    right_rect=right_rect,
                    fitting_mode=project.print_settings.fitting_mode,
                )

            if include_back:
                cls._append_imposed_side(
                    output_document=output_document,
                    side=sheet.back,
                    stream=stream,
                    source_documents=source_documents,
                    sheet_width=sheet_width,
                    sheet_height=sheet_height,
                    left_rect=left_rect,
                    right_rect=right_rect,
                    fitting_mode=project.print_settings.fitting_mode,
                )

    @staticmethod
    def _append_blank_sheet(
        *,
        output_document: pymupdf.Document,
        sheet_width: float,
        sheet_height: float,
    ) -> None:
        """Append both blank sides of one physical separator sheet."""

        output_document.new_page(
            width=sheet_width,
            height=sheet_height,
        )
        output_document.new_page(
            width=sheet_width,
            height=sheet_height,
        )

    @staticmethod
    def _save_document(
        *,
        output_document: pymupdf.Document,
        temporary_path: Path,
        output_path: Path,
    ) -> None:
        """Save a document atomically to its final path."""

        try:
            output_document.save(
                temporary_path,
                garbage=3,
                deflate=True,
            )
        except Exception as exc:
            raise SignaturePdfExportError(
                f'Could not write temporary PDF "{temporary_path}": {exc}'
            ) from exc

        try:
            temporary_path.replace(output_path)
        except OSError as exc:
            SignaturePdfExporter._remove_temporary_file(temporary_path)
            raise SignaturePdfExportError(
                f'Could not save "{output_path}": {exc}'
            ) from exc

    @staticmethod
    def _remove_temporary_file(path: Path) -> None:
        """Remove a stale or failed temporary output file."""

        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise SignaturePdfExportError(
                f'Could not remove temporary file "{path}": {exc}'
            ) from exc

    @staticmethod
    def _filename_slug(value: str) -> str:
        """Return a filesystem-friendly lowercase name."""

        slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            value.strip().lower(),
        ).strip("-")

        return slug or "book"

    @classmethod
    def _append_imposed_side(
        cls,
        *,
        output_document: pymupdf.Document,
        side: ImposedSide,
        stream: LogicalPageStream,
        source_documents: dict[Path, pymupdf.Document],
        sheet_width: float,
        sheet_height: float,
        left_rect: pymupdf.Rect,
        right_rect: pymupdf.Rect,
        fitting_mode: PageFittingMode,
    ) -> None:
        """Append one physical sheet side to the output document."""

        output_page = output_document.new_page(
            width=sheet_width,
            height=sheet_height,
        )

        cls._place_logical_page(
            output_page=output_page,
            destination_rect=left_rect,
            logical_page=stream[side.left_page_index],
            source_documents=source_documents,
            fitting_mode=fitting_mode,
        )

        cls._place_logical_page(
            output_page=output_page,
            destination_rect=right_rect,
            logical_page=stream[side.right_page_index],
            source_documents=source_documents,
            fitting_mode=fitting_mode,
        )

    @classmethod
    def _place_logical_page(
        cls,
        *,
        output_page: pymupdf.Page,
        destination_rect: pymupdf.Rect,
        logical_page: LogicalPage,
        source_documents: dict[Path, pymupdf.Document],
        fitting_mode: PageFittingMode,
    ) -> None:
        """Place a source page using the selected fitting behaviour."""

        if isinstance(logical_page, BlankLogicalPage):
            return

        if not isinstance(logical_page, SourceLogicalPage):
            raise SignaturePdfExportError(
                f"Unsupported logical page type: "
                f"{type(logical_page).__name__}."
            )

        try:
            source_document = source_documents[
                logical_page.document_path
            ]
        except KeyError as exc:
            raise SignaturePdfExportError(
                f'Source PDF "{logical_page.document_path}" was not opened.'
            ) from exc

        page_number = logical_page.document_page_index

        if page_number < 0 or page_number >= source_document.page_count:
            raise SignaturePdfExportError(
                f"Source page index {page_number} is outside "
                f'"{logical_page.document_path}".'
            )

        if fitting_mode is PageFittingMode.FIT:
            output_page.show_pdf_page(
                destination_rect,
                source_document,
                page_number,
                keep_proportion=True,
                overlay=True,
            )
            return

        if fitting_mode is PageFittingMode.FILL_AND_CROP:
            source_page = source_document[page_number]

            clip_rect = cls._centred_crop_rect(
                source_page.rect,
                destination_rect,
            )

            output_page.show_pdf_page(
                destination_rect,
                source_document,
                page_number,
                clip=clip_rect,
                keep_proportion=True,
                overlay=True,
            )
            return

        raise SignaturePdfExportError(
            f"Unsupported page fitting mode: {fitting_mode}."
        )

    @classmethod
    def _open_source_documents(
        cls,
        project: BookProject,
        *,
        stack: ExitStack,
    ) -> dict[Path, pymupdf.Document]:
        """Open each source PDF once for the complete export."""

        documents: dict[Path, pymupdf.Document] = {}

        for document_input in project.documents:
            path = document_input.path

            if path in documents:
                continue

            if not path.exists():
                raise SignaturePdfExportError(
                    f'Source PDF does not exist: "{path}".'
                )

            try:
                document = pymupdf.open(path)
            except Exception as exc:
                raise SignaturePdfExportError(
                    f'Could not open source PDF "{path}": {exc}'
                ) from exc

            stack.callback(document.close)

            if document.needs_pass:
                raise SignaturePdfExportError(
                    f'Source PDF is password protected: "{path}".'
                )

            if document.page_count != document_input.page_count:
                raise SignaturePdfExportError(
                    f'Source PDF "{path}" now contains '
                    f"{document.page_count} pages, but the project "
                    f"expects {document_input.page_count}."
                )

            documents[path] = document

        return documents

    @classmethod
    def _sheet_size_points(
        cls,
        paper_size: PaperSize,
    ) -> tuple[float, float]:
        """Return the selected physical sheet size in landscape points."""

        try:
            portrait_width_mm, portrait_height_mm = (
                cls._PAPER_SIZES_MM[paper_size]
            )
        except KeyError as exc:
            raise SignaturePdfExportError(
                f"Unsupported paper size: {paper_size}."
            ) from exc

        landscape_width = portrait_height_mm * cls._MM_TO_POINTS
        landscape_height = portrait_width_mm * cls._MM_TO_POINTS

        return landscape_width, landscape_height

    @classmethod
    def _page_destination_rects(
        cls,
        project: BookProject,
        *,
        sheet_width: float,
        sheet_height: float,
    ) -> tuple[pymupdf.Rect, pymupdf.Rect]:
        """Calculate the usable left and right finished-page rectangles."""

        margins = project.print_settings.margins

        binding = margins.binding_mm * cls._MM_TO_POINTS
        outer = margins.outer_mm * cls._MM_TO_POINTS
        top = margins.top_mm * cls._MM_TO_POINTS
        bottom = margins.bottom_mm * cls._MM_TO_POINTS

        half_width = sheet_width / 2.0

        left_rect = pymupdf.Rect(
            outer,
            top,
            half_width - binding,
            sheet_height - bottom,
        )

        right_rect = pymupdf.Rect(
            half_width + binding,
            top,
            sheet_width - outer,
            sheet_height - bottom,
        )

        if left_rect.is_empty or right_rect.is_empty:
            raise SignaturePdfExportError(
                "The selected margins leave no usable page area."
            )

        if left_rect.width <= 0 or left_rect.height <= 0:
            raise SignaturePdfExportError(
                "The selected margins leave no usable left-page area."
            )

        if right_rect.width <= 0 or right_rect.height <= 0:
            raise SignaturePdfExportError(
                "The selected margins leave no usable right-page area."
            )

        return left_rect, right_rect

    @staticmethod
    def _centred_crop_rect(
        source_rect: pymupdf.Rect,
        destination_rect: pymupdf.Rect,
    ) -> pymupdf.Rect:
        """Crop a source page centrally to fill a destination rectangle."""

        source_width = source_rect.width
        source_height = source_rect.height
        destination_width = destination_rect.width
        destination_height = destination_rect.height

        if source_width <= 0 or source_height <= 0:
            raise SignaturePdfExportError(
                "The source PDF page has an invalid page size."
            )

        if destination_width <= 0 or destination_height <= 0:
            raise SignaturePdfExportError(
                "The destination page area has an invalid size."
            )

        destination_ratio = destination_width / destination_height
        source_ratio = source_width / source_height

        if source_ratio > destination_ratio:
            cropped_width = source_height * destination_ratio
            horizontal_trim = (source_width - cropped_width) / 2.0

            return pymupdf.Rect(
                source_rect.x0 + horizontal_trim,
                source_rect.y0,
                source_rect.x1 - horizontal_trim,
                source_rect.y1,
            )

        if source_ratio < destination_ratio:
            cropped_height = source_width / destination_ratio
            vertical_trim = (source_height - cropped_height) / 2.0

            return pymupdf.Rect(
                source_rect.x0,
                source_rect.y0 + vertical_trim,
                source_rect.x1,
                source_rect.y1 - vertical_trim,
            )

        return pymupdf.Rect(source_rect)

    @staticmethod
    def _validate_inputs(
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
    ) -> None:
        """Validate that the supplied structures describe the same book."""

        if not project.documents:
            raise SignaturePdfExportError(
                "The project must contain at least one PDF."
            )

        if not imposition.signatures:
            raise SignaturePdfExportError(
                "The imposition must contain at least one signature."
            )

        if stream.page_count != project.total_page_count:
            raise SignaturePdfExportError(
                f"The logical stream contains {stream.page_count} "
                f"pages, but the project contains "
                f"{project.total_page_count}."
            )

        if imposition.total_page_count != stream.page_count:
            raise SignaturePdfExportError(
                f"The imposition contains "
                f"{imposition.total_page_count} pages, but the "
                f"logical stream contains {stream.page_count}."
            )

        expected_indices = set(range(stream.page_count))
        imposed_indices = imposition.page_indices

        if len(imposed_indices) != len(set(imposed_indices)):
            raise SignaturePdfExportError(
                "The imposition contains duplicate logical pages."
            )

        if set(imposed_indices) != expected_indices:
            raise SignaturePdfExportError(
                "The imposition does not contain every logical page."
            )
