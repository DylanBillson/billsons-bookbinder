"""Render imposed book pages as in-memory preview images."""

from contextlib import ExitStack
from pathlib import Path

import pymupdf

from app.models import (
    BlankLogicalPage,
    BookImposition,
    BookPreview,
    BookProject,
    ImposedSide,
    ImposedSignature,
    LogicalPage,
    LogicalPageStream,
    PageFittingMode,
    PaperSize,
    RenderedPreviewPage,
    SheetSide,
    SignaturePreview,
    SourceLogicalPage,
)


class PdfPreviewRenderError(RuntimeError):
    """Raised when an imposed preview cannot be rendered."""


class PdfPreviewRenderer:
    """Render imposed sheet sides into in-memory PNG images."""

    DEFAULT_DPI = 110
    MINIMUM_DPI = 36
    MAXIMUM_DPI = 300

    _MM_TO_POINTS = 72.0 / 25.4

    _PAPER_SIZES_MM: dict[PaperSize, tuple[float, float]] = {
        PaperSize.A3: (297.0, 420.0),
        PaperSize.A4: (210.0, 297.0),
        PaperSize.A5: (148.0, 210.0),
    }

    @classmethod
    def render_book(
        cls,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        *,
        dpi: int = DEFAULT_DPI,
    ) -> BookPreview:
        """Render every imposed signature in the book."""

        cls._validate_render_request(
            project,
            stream,
            imposition,
            dpi=dpi,
        )

        rendered_signatures: list[SignaturePreview] = []

        with ExitStack() as stack:
            source_documents = cls._open_source_documents(
                project,
                stack=stack,
            )

            for signature in imposition.signatures:
                rendered_signatures.append(
                    cls._render_signature(
                        project=project,
                        stream=stream,
                        signature=signature,
                        source_documents=source_documents,
                        dpi=dpi,
                    )
                )

        return BookPreview(
            signatures=tuple(rendered_signatures),
        )

    @classmethod
    def render_signature(
        cls,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        *,
        signature_number: int,
        dpi: int = DEFAULT_DPI,
    ) -> SignaturePreview:
        """Render one signature selected by its one-based number."""

        cls._validate_render_request(
            project,
            stream,
            imposition,
            dpi=dpi,
        )

        signature = cls._find_signature(
            imposition,
            signature_number=signature_number,
        )

        with ExitStack() as stack:
            source_documents = cls._open_source_documents(
                project,
                stack=stack,
            )

            return cls._render_signature(
                project=project,
                stream=stream,
                signature=signature,
                source_documents=source_documents,
                dpi=dpi,
            )

    @classmethod
    def render_page(
        cls,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        *,
        signature_number: int,
        output_page_index: int,
        dpi: int = DEFAULT_DPI,
    ) -> RenderedPreviewPage:
        """Render one imposed output side without rendering its siblings."""

        cls._validate_render_request(
            project,
            stream,
            imposition,
            dpi=dpi,
        )

        signature = cls._find_signature(
            imposition,
            signature_number=signature_number,
        )

        sheet_count = signature.sheet_count
        output_page_count = sheet_count * 2

        if output_page_index < 0 or output_page_index >= output_page_count:
            raise PdfPreviewRenderError(
                f"Output page index {output_page_index} is outside "
                f"the valid range 0–{output_page_count - 1} for "
                f"signature {signature_number}."
            )

        sheet_index, side_offset = divmod(output_page_index, 2)
        sheet = signature.sheets[sheet_index]

        if side_offset == 0:
            side = sheet.front
            side_name = SheetSide.FRONT
        else:
            side = sheet.back
            side_name = SheetSide.BACK

        with ExitStack() as stack:
            source_documents = cls._open_source_documents(
                project,
                stack=stack,
            )

            return cls._render_side(
                project=project,
                stream=stream,
                imposed_side=side,
                side_name=side_name,
                signature_number=signature.number,
                sheet_number=sheet.number,
                output_page_index=output_page_index,
                source_documents=source_documents,
                dpi=dpi,
            )

    @classmethod
    def _render_signature(
        cls,
        *,
        project: BookProject,
        stream: LogicalPageStream,
        signature: ImposedSignature,
        source_documents: dict[Path, pymupdf.Document],
        dpi: int,
    ) -> SignaturePreview:
        """Render every side in one signature."""

        rendered_pages: list[RenderedPreviewPage] = []
        output_page_index = 0

        for sheet in signature.sheets:
            rendered_pages.append(
                cls._render_side(
                    project=project,
                    stream=stream,
                    imposed_side=sheet.front,
                    side_name=SheetSide.FRONT,
                    signature_number=signature.number,
                    sheet_number=sheet.number,
                    output_page_index=output_page_index,
                    source_documents=source_documents,
                    dpi=dpi,
                )
            )
            output_page_index += 1

            rendered_pages.append(
                cls._render_side(
                    project=project,
                    stream=stream,
                    imposed_side=sheet.back,
                    side_name=SheetSide.BACK,
                    signature_number=signature.number,
                    sheet_number=sheet.number,
                    output_page_index=output_page_index,
                    source_documents=source_documents,
                    dpi=dpi,
                )
            )
            output_page_index += 1

        preview = SignaturePreview(
            signature_number=signature.number,
            sheet_count=signature.sheet_count,
            pages=tuple(rendered_pages),
        )

        if preview.page_count != preview.expected_page_count:
            raise PdfPreviewRenderError(
                f"Signature {signature.number} produced "
                f"{preview.page_count} preview pages, but "
                f"{preview.expected_page_count} were expected."
            )

        return preview

    @classmethod
    def _render_side(
        cls,
        *,
        project: BookProject,
        stream: LogicalPageStream,
        imposed_side: ImposedSide,
        side_name: SheetSide,
        signature_number: int,
        sheet_number: int,
        output_page_index: int,
        source_documents: dict[Path, pymupdf.Document],
        dpi: int,
    ) -> RenderedPreviewPage:
        """Render one imposed side to PNG bytes."""

        sheet_width, sheet_height = cls._sheet_size_points(project.print_settings.paper_size)

        left_rect, right_rect = cls._page_destination_rects(
            project,
            sheet_width=sheet_width,
            sheet_height=sheet_height,
        )

        output_document = pymupdf.open()

        try:
            output_page = output_document.new_page(
                width=sheet_width,
                height=sheet_height,
            )

            cls._place_logical_page(
                output_page=output_page,
                destination_rect=left_rect,
                logical_page=stream[imposed_side.left_page_index],
                source_documents=source_documents,
                fitting_mode=project.print_settings.fitting_mode,
            )

            cls._place_logical_page(
                output_page=output_page,
                destination_rect=right_rect,
                logical_page=stream[imposed_side.right_page_index],
                source_documents=source_documents,
                fitting_mode=project.print_settings.fitting_mode,
            )

            pixmap = output_page.get_pixmap(
                dpi=dpi,
                colorspace=pymupdf.csRGB,
                alpha=False,
            )

            png_bytes = pixmap.tobytes("png")

            return RenderedPreviewPage(
                signature_number=signature_number,
                sheet_number=sheet_number,
                side=side_name,
                output_page_index=output_page_index,
                left_page_number=imposed_side.left_page_number,
                right_page_number=imposed_side.right_page_number,
                width_pixels=pixmap.width,
                height_pixels=pixmap.height,
                png_bytes=png_bytes,
            )
        except PdfPreviewRenderError:
            raise
        except Exception as exc:
            raise PdfPreviewRenderError(
                f"Could not render signature {signature_number}, "
                f"sheet {sheet_number}, {side_name.value}: {exc}"
            ) from exc
        finally:
            output_document.close()

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
        """Place a source page or leave an explicit blank slot."""

        if isinstance(logical_page, BlankLogicalPage):
            return

        if not isinstance(logical_page, SourceLogicalPage):
            raise PdfPreviewRenderError(
                f"Unsupported logical page type: {type(logical_page).__name__}."
            )

        try:
            source_document = source_documents[logical_page.document_path]
        except KeyError as exc:
            raise PdfPreviewRenderError(
                f'Source PDF "{logical_page.document_path}" was not opened.'
            ) from exc

        source_page_index = logical_page.document_page_index

        if source_page_index < 0 or source_page_index >= source_document.page_count:
            raise PdfPreviewRenderError(
                f"Source page index {source_page_index} is invalid "
                f'for "{logical_page.document_path}".'
            )

        if fitting_mode is PageFittingMode.FIT:
            output_page.show_pdf_page(
                destination_rect,
                source_document,
                source_page_index,
                keep_proportion=True,
                overlay=True,
            )
            return

        if fitting_mode is PageFittingMode.FILL_AND_CROP:
            source_page = source_document[source_page_index]

            clip_rect = cls._centred_crop_rect(
                source_page.rect,
                destination_rect,
            )

            output_page.show_pdf_page(
                destination_rect,
                source_document,
                source_page_index,
                clip=clip_rect,
                keep_proportion=True,
                overlay=True,
            )
            return

        raise PdfPreviewRenderError(f"Unsupported page fitting mode: {fitting_mode}.")

    @classmethod
    def _open_source_documents(
        cls,
        project: BookProject,
        *,
        stack: ExitStack,
    ) -> dict[Path, pymupdf.Document]:
        """Open each unique source document once."""

        documents: dict[Path, pymupdf.Document] = {}

        for document_input in project.documents:
            path = document_input.path

            if path in documents:
                continue

            if not path.exists():
                raise PdfPreviewRenderError(f'Source PDF does not exist: "{path}".')

            try:
                document = pymupdf.open(path)
            except Exception as exc:
                raise PdfPreviewRenderError(f'Could not open source PDF "{path}": {exc}') from exc

            stack.callback(document.close)

            if document.needs_pass:
                raise PdfPreviewRenderError(f'Source PDF is password protected: "{path}".')

            if document.page_count != document_input.page_count:
                raise PdfPreviewRenderError(
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
        """Return landscape sheet dimensions in PDF points."""

        try:
            portrait_width_mm, portrait_height_mm = cls._PAPER_SIZES_MM[paper_size]
        except KeyError as exc:
            raise PdfPreviewRenderError(f"Unsupported paper size: {paper_size}.") from exc

        return (
            portrait_height_mm * cls._MM_TO_POINTS,
            portrait_width_mm * cls._MM_TO_POINTS,
        )

    @classmethod
    def _page_destination_rects(
        cls,
        project: BookProject,
        *,
        sheet_width: float,
        sheet_height: float,
    ) -> tuple[pymupdf.Rect, pymupdf.Rect]:
        """Calculate usable left and right page rectangles."""

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
            raise PdfPreviewRenderError("The selected margins leave no usable page area.")

        if left_rect.width <= 0 or left_rect.height <= 0:
            raise PdfPreviewRenderError("The selected margins leave no usable left-page area.")

        if right_rect.width <= 0 or right_rect.height <= 0:
            raise PdfPreviewRenderError("The selected margins leave no usable right-page area.")

        return left_rect, right_rect

    @staticmethod
    def _centred_crop_rect(
        source_rect: pymupdf.Rect,
        destination_rect: pymupdf.Rect,
    ) -> pymupdf.Rect:
        """Crop a source page centrally to fill its destination."""

        if source_rect.width <= 0 or source_rect.height <= 0:
            raise PdfPreviewRenderError("The source page has invalid dimensions.")

        if destination_rect.width <= 0 or destination_rect.height <= 0:
            raise PdfPreviewRenderError("The destination rectangle has invalid dimensions.")

        source_ratio = source_rect.width / source_rect.height
        destination_ratio = destination_rect.width / destination_rect.height

        if source_ratio > destination_ratio:
            cropped_width = source_rect.height * destination_ratio
            horizontal_trim = (source_rect.width - cropped_width) / 2.0

            return pymupdf.Rect(
                source_rect.x0 + horizontal_trim,
                source_rect.y0,
                source_rect.x1 - horizontal_trim,
                source_rect.y1,
            )

        cropped_height = source_rect.width / destination_ratio
        vertical_trim = (source_rect.height - cropped_height) / 2.0

        return pymupdf.Rect(
            source_rect.x0,
            source_rect.y0 + vertical_trim,
            source_rect.x1,
            source_rect.y1 - vertical_trim,
        )

    @classmethod
    def _validate_render_request(
        cls,
        project: BookProject,
        stream: LogicalPageStream,
        imposition: BookImposition,
        *,
        dpi: int,
    ) -> None:
        """Validate structures before beginning an expensive render."""

        if not isinstance(dpi, int):
            raise PdfPreviewRenderError("Preview DPI must be an integer.")

        if dpi < cls.MINIMUM_DPI or dpi > cls.MAXIMUM_DPI:
            raise PdfPreviewRenderError(
                f"Preview DPI must be between {cls.MINIMUM_DPI} and {cls.MAXIMUM_DPI}."
            )

        if not project.documents:
            raise PdfPreviewRenderError("The project must contain at least one PDF.")

        if stream.page_count != project.total_page_count:
            raise PdfPreviewRenderError(
                f"The logical stream contains {stream.page_count} "
                f"pages, but the project contains "
                f"{project.total_page_count}."
            )

        if imposition.total_page_count != stream.page_count:
            raise PdfPreviewRenderError(
                f"The imposition contains "
                f"{imposition.total_page_count} pages, but the "
                f"logical stream contains {stream.page_count}."
            )

        expected_indices = set(range(stream.page_count))
        imposed_indices = imposition.page_indices

        if len(imposed_indices) != len(set(imposed_indices)):
            raise PdfPreviewRenderError("The imposition contains duplicate logical pages.")

        if set(imposed_indices) != expected_indices:
            raise PdfPreviewRenderError("The imposition does not contain every logical page.")

    @staticmethod
    def _find_signature(
        imposition: BookImposition,
        *,
        signature_number: int,
    ) -> ImposedSignature:
        """Find one imposed signature by number."""

        for signature in imposition.signatures:
            if signature.number == signature_number:
                return signature

        raise PdfPreviewRenderError(f"No imposed signature has number {signature_number}.")
