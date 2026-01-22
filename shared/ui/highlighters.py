"""
Syntax highlighters for text editors.
"""

import re
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class ModsListHighlighter(QSyntaxHighlighter):
    """
    Highlights common mods.txt formatting problems.
    
    Problems detected:
    - Spaces around semicolons (e.g., " @Mod ;" or "; @Mod")
    - Duplicate semicolons (e.g., ";;")
    """

    def __init__(self, parent):
        super().__init__(parent)
        
        # Warning format - orange wave underline
        self._fmt_problem = QTextCharFormat()
        self._fmt_problem.setUnderlineColor(QColor("#f0ad4e"))
        self._fmt_problem.setUnderlineStyle(QTextCharFormat.WaveUnderline)

        # Error format - red wave underline
        self._fmt_error = QTextCharFormat()
        self._fmt_error.setUnderlineColor(QColor("#e53935"))
        self._fmt_error.setUnderlineStyle(QTextCharFormat.WaveUnderline)

    def highlightBlock(self, text: str):
        # Spaces before semicolon: " @Mod ;"
        for match in re.finditer(r"\s+;", text):
            self.setFormat(match.start(), match.end() - match.start() - 1, self._fmt_problem)

        # Spaces after semicolon: "; @Mod"
        for match in re.finditer(r";\s+", text):
            self.setFormat(match.start() + 1, match.end() - match.start() - 1, self._fmt_problem)

        # Duplicate semicolons: ";;" (usually indicates empty entry)
        for match in re.finditer(r";{2,}", text):
            self.setFormat(match.start(), match.end() - match.start(), self._fmt_error)
