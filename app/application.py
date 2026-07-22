"""Billson's Bookbinder application startup."""

import sys

from PySide6.QtWidgets import QApplication

from app.models import BookProject
from app.ui import MainWindow
from app.version import (
    APP_NAME,
    APP_VERSION,
    ORGANISATION_DOMAIN,
    ORGANISATION_NAME,
)


def main() -> int:
    """Start the desktop application."""

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(ORGANISATION_NAME)
    application.setOrganizationDomain(ORGANISATION_DOMAIN)

    project = BookProject()
    window = MainWindow(project)
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())