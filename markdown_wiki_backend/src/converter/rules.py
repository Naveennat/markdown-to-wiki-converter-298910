from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WikiMappings:
    """
    MediaWiki-style mappings (best-effort).

    Notes:
    - We keep mappings simple and predictable.
    - For inline code we emit <code>...</code> to avoid interfering with bold/italic quotes.
    - For fenced code blocks we emit <pre>...</pre> to preserve content verbatim.
    """

    heading_marks: tuple[str, ...] = ("=", "==", "===", "====", "=====", "======")
    hr: str = "----"
    bold: str = "'''"
    italic: str = "''"

    # Using HTML-ish tags is widely accepted in MediaWiki and helps preserve content.
    inline_code_open: str = "<code>"
    inline_code_close: str = "</code>"
    pre_open: str = "<pre>"
    pre_close: str = "</pre>"

    # Tables (very basic, best-effort)
    table_open: str = '{| class="wikitable"'
    table_close: str = "|}"
    table_row: str = "|-"


DEFAULT_MAPPINGS = WikiMappings()


def escape_nowiki(text: str) -> str:
    """
    Escape text content for safe inclusion in wiki.

    We keep escaping minimal and best-effort:
    - MediaWiki doesn't require escaping most characters in plain text.
    - In tables, "|" and "!" can be structural; the engine will try to keep them safe.
    """
    return text


def safe_table_cell_text(text: str) -> str:
    """
    Make table cell text safer by avoiding accidental cell separators.

    This is best-effort; we don't try to fully parse nested wiki markup.
    """
    # Pipe in cell content can break tables; wrap with <nowiki>...</nowiki>
    if "|" in text or "!!" in text or "||" in text:
        return f"<nowiki>{text}</nowiki>"
    return text
