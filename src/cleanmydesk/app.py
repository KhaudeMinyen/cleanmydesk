"""Start the CleanMyDesk app."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cleanmydesk.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setOrganizationName("CleanMyDesk")
    app.setApplicationName("CleanMyDesk")
    window = MainWindow()
    # A project file can be passed on the command line to open it.
    if len(argv) > 1:
        window.open_path(Path(argv[1]))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
