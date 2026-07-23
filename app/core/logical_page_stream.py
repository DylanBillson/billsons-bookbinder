"""Build the ordered logical page stream for a book project."""

from app.models import (
    BlankLogicalPage,
    BlankPages,
    BookProject,
    InputDocument,
    LogicalPage,
    LogicalPageStream,
    SourceLogicalPage,
)


class LogicalPageStreamError(ValueError):
    """Raised when a logical page stream cannot be built safely."""


class LogicalPageStreamBuilder:
    """Expand ordered project inputs into individual logical pages."""

    @classmethod
    def create(cls, project: BookProject) -> LogicalPageStream:
        """Create the complete logical page stream for a project."""

        if not project.inputs:
            raise LogicalPageStreamError("The project does not contain any input entries.")

        if not project.documents:
            raise LogicalPageStreamError("The project must contain at least one PDF.")

        pages: list[LogicalPage] = []
        next_book_page_index = 0

        for input_index, item in enumerate(project.inputs):
            if isinstance(item, InputDocument):
                document_pages = cls._expand_document(
                    item,
                    input_index=input_index,
                    start_book_page_index=next_book_page_index,
                )
                pages.extend(document_pages)
                next_book_page_index += item.page_count
                continue

            if isinstance(item, BlankPages):
                blank_pages = cls._expand_blank_pages(
                    item,
                    input_index=input_index,
                    start_book_page_index=next_book_page_index,
                )
                pages.extend(blank_pages)
                next_book_page_index += item.quantity
                continue

            raise LogicalPageStreamError(
                f"Input entry {input_index + 1} has an unsupported type: {type(item).__name__}."
            )

        stream = LogicalPageStream(pages=tuple(pages))
        cls._validate_stream(project, stream)

        return stream

    @staticmethod
    def _expand_document(
        document: InputDocument,
        *,
        input_index: int,
        start_book_page_index: int,
    ) -> tuple[SourceLogicalPage, ...]:
        """Expand one PDF input into individual logical pages."""

        if document.page_count < 1:
            raise LogicalPageStreamError(
                f'PDF "{document.filename}" must contain at least one page.'
            )

        return tuple(
            SourceLogicalPage(
                book_page_index=start_book_page_index + document_page_index,
                document_path=document.path,
                document_page_index=document_page_index,
                input_index=input_index,
            )
            for document_page_index in range(document.page_count)
        )

    @staticmethod
    def _expand_blank_pages(
        blank_pages: BlankPages,
        *,
        input_index: int,
        start_book_page_index: int,
    ) -> tuple[BlankLogicalPage, ...]:
        """Expand one blank-page block into individual logical pages."""

        if blank_pages.quantity < 1:
            raise LogicalPageStreamError(
                f"Blank-page block {input_index + 1} must contain at least one page."
            )

        return tuple(
            BlankLogicalPage(
                book_page_index=start_book_page_index + blank_index,
                input_index=input_index,
                blank_index=blank_index,
            )
            for blank_index in range(blank_pages.quantity)
        )

    @staticmethod
    def _validate_stream(
        project: BookProject,
        stream: LogicalPageStream,
    ) -> None:
        """Ensure the generated stream exactly matches the project."""

        if stream.page_count != project.total_page_count:
            raise LogicalPageStreamError(
                
                    f"The logical page stream contains "
                    f"{stream.page_count} pages, but the project contains "
                    f"{project.total_page_count} pages."
                
            )

        if stream.source_page_count != project.source_pdf_page_count:
            raise LogicalPageStreamError(
                
                    f"The logical page stream contains "
                    f"{stream.source_page_count} source pages, but the "
                    f"project contains {project.source_pdf_page_count}."
                
            )

        if stream.blank_page_count != project.blank_page_count:
            raise LogicalPageStreamError(
                
                    f"The logical page stream contains "
                    f"{stream.blank_page_count} blank pages, but the "
                    f"project contains {project.blank_page_count}."
                
            )

        expected_indices = tuple(range(project.total_page_count))
        actual_indices = tuple(page.book_page_index for page in stream.pages)

        if actual_indices != expected_indices:
            raise LogicalPageStreamError("The logical page stream is not contiguous.")
