from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

from src.converter.rules import DEFAULT_MAPPINGS, WikiMappings, safe_table_cell_text


@dataclass
class _ListCtx:
    """Internal list context used for nested list rendering."""

    ordered: bool
    # Whether we have emitted at least one list item at this level
    started: bool = False


@dataclass
class _RenderState:
    """Internal render state for conversion."""

    mappings: WikiMappings = DEFAULT_MAPPINGS
    warnings: List[str] = field(default_factory=list)
    out: List[str] = field(default_factory=list)

    # Stack of list contexts; nesting is represented by repeating bullet markers.
    list_stack: List[_ListCtx] = field(default_factory=list)

    # Table state (very basic)
    in_table: bool = False
    current_row_has_cells: bool = False
    in_thead: bool = False

    # Inline formatting state
    italic_open: bool = False
    bold_open: bool = False
    code_inline_open: bool = False

    def push(self, s: str) -> None:
        self.out.append(s)

    def push_line(self, s: str = "") -> None:
        self.out.append(s + "\n")

    def get_text(self) -> str:
        return "".join(self.out)


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _mk_md() -> MarkdownIt:
    """
    Create the MarkdownIt parser used for conversion.

    We enable the commonmark preset + tables where possible.
    """
    md = MarkdownIt("commonmark")

    # Enable table support if available in this markdown-it-py build.
    # (markdown-it-py includes a 'table' rule but is not always enabled by default)
    try:
        md.enable("table")
    except Exception:
        # Keep going; we'll still do best-effort conversion.
        pass

    return md


def _close_any_open_inline(state: _RenderState) -> None:
    """Close any open inline markers to avoid leaking formatting."""
    if state.code_inline_open:
        state.push(state.mappings.inline_code_close)
        state.code_inline_open = False
    if state.bold_open:
        state.push(state.mappings.bold)
        state.bold_open = False
    if state.italic_open:
        state.push(state.mappings.italic)
        state.italic_open = False


def _emit_list_item_prefix(state: _RenderState) -> None:
    """Emit MediaWiki list prefix based on nesting and ordered/unordered stack."""
    if not state.list_stack:
        return
    prefix = ""
    for ctx in state.list_stack:
        prefix += "#" if ctx.ordered else "*"
    state.push(prefix + " ")


def _render_tokens(tokens: List[Token], state: _RenderState) -> None:
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        t = tok.type

        # --- Block structure tokens ---
        if t == "heading_open":
            # Close any lingering inline.
            _close_any_open_inline(state)
            level = int(tok.tag[1]) if tok.tag and tok.tag.startswith("h") else 1
            level = max(1, min(6, level))
            mark = state.mappings.heading_marks[level - 1]
            # Heading content will come in the following inline token.
            state.push(mark + " ")
        elif t == "heading_close":
            level = int(tok.tag[1]) if tok.tag and tok.tag.startswith("h") else 1
            level = max(1, min(6, level))
            mark = state.mappings.heading_marks[level - 1]
            state.push(" " + mark)
            state.push_line()
            state.push_line()
        elif t == "paragraph_open":
            # Ensure paragraph starts on a new line if needed.
            # Do not auto-insert in tables/lists; those have their own newlines.
            pass
        elif t == "paragraph_close":
            # Paragraph separation (blank line) except when in lists (list items already newline-delimited).
            if not state.list_stack and not state.in_table:
                state.push_line()
                state.push_line()
            else:
                state.push_line()
        elif t == "blockquote_open":
            _close_any_open_inline(state)
            # MediaWiki blockquote is commonly represented by leading ":" per line.
            # We'll prefix ":" at start of each paragraph line within until close.
            state.push_line()  # spacing
        elif t == "blockquote_close":
            _close_any_open_inline(state)
            state.push_line()
        elif t == "hr":
            _close_any_open_inline(state)
            state.push_line(state.mappings.hr)
            state.push_line()
        elif t == "bullet_list_open":
            state.list_stack.append(_ListCtx(ordered=False))
            state.push_line()
        elif t == "bullet_list_close":
            _close_any_open_inline(state)
            if state.list_stack:
                state.list_stack.pop()
            state.push_line()
        elif t == "ordered_list_open":
            state.list_stack.append(_ListCtx(ordered=True))
            state.push_line()
        elif t == "ordered_list_close":
            _close_any_open_inline(state)
            if state.list_stack:
                state.list_stack.pop()
            state.push_line()
        elif t == "list_item_open":
            _close_any_open_inline(state)
            _emit_list_item_prefix(state)
        elif t == "list_item_close":
            _close_any_open_inline(state)
            # Ensure a newline after each list item.
            if not state.get_text().endswith("\n"):
                state.push_line()
        elif t == "fence":
            _close_any_open_inline(state)
            info = (tok.info or "").strip()
            content = tok.content or ""
            # Preserve content verbatim.
            state.push_line(state.mappings.pre_open + (f' data-lang="{info}"' if info else ""))
            # Ensure single trailing newline inside pre for neatness.
            content = _normalize_newlines(content)
            if content.endswith("\n"):
                state.push(content)
            else:
                state.push(content + "\n")
            state.push_line(state.mappings.pre_close)
            state.push_line()
        elif t == "code_block":
            _close_any_open_inline(state)
            content = _normalize_newlines(tok.content or "")
            state.push_line(state.mappings.pre_open)
            state.push(content if content.endswith("\n") else content + "\n")
            state.push_line(state.mappings.pre_close)
            state.push_line()

        # --- Tables (best-effort; markdown-it token types: table_open/close etc.) ---
        elif t == "table_open":
            _close_any_open_inline(state)
            state.in_table = True
            state.push_line(state.mappings.table_open)
        elif t == "table_close":
            _close_any_open_inline(state)
            # Close any dangling row
            state.push_line(state.mappings.table_close)
            state.push_line()
            state.in_table = False
            state.in_thead = False
            state.current_row_has_cells = False
        elif t == "thead_open":
            state.in_thead = True
        elif t == "thead_close":
            state.in_thead = False
        elif t == "tbody_open":
            pass
        elif t == "tbody_close":
            pass
        elif t == "tr_open":
            state.current_row_has_cells = False
            state.push_line(state.mappings.table_row)
        elif t == "tr_close":
            # Ensure row ends with newline (cells already emit lines).
            state.current_row_has_cells = False
        elif t in ("th_open", "td_open"):
            # Cell content arrives as nested inline tokens between open/close.
            # We'll start a new cell line: "!" for headers, "|" for data.
            # MediaWiki also supports "!!" / "||", but per-line is simpler.
            marker = "!" if (t == "th_open" or state.in_thead) else "|"
            state.push(marker + " ")
            state.current_row_has_cells = True
        elif t in ("th_close", "td_close"):
            # End cell with newline; the next cell starts its own line.
            state.push_line()

        # --- Inline tokens and text ---
        elif t == "inline":
            # Render children tokens recursively.
            if tok.children:
                _render_tokens(tok.children, state)
        elif t == "text":
            txt = tok.content or ""
            if state.in_table:
                txt = safe_table_cell_text(txt)
            if state.list_stack and state.get_text().endswith("* ") or state.get_text().endswith("# "):
                # nothing special; keep text
                pass
            state.push(txt)
        elif t == "softbreak":
            # In MediaWiki, softbreak generally becomes newline; in paragraphs it behaves like a space.
            # We'll use newline inside lists/tables/blockquote-ish contexts; otherwise space.
            if state.list_stack or state.in_table:
                state.push_line()
            else:
                state.push("\n")
        elif t == "hardbreak":
            state.push("\n")
        elif t == "em_open":
            state.push(state.mappings.italic)
            state.italic_open = True
        elif t == "em_close":
            state.push(state.mappings.italic)
            state.italic_open = False
        elif t == "strong_open":
            state.push(state.mappings.bold)
            state.bold_open = True
        elif t == "strong_close":
            state.push(state.mappings.bold)
            state.bold_open = False
        elif t == "code_inline":
            # Preserve inline code content; wrap in <code>...</code>
            content = tok.content or ""
            state.push(state.mappings.inline_code_open)
            state.push(content)
            state.push(state.mappings.inline_code_close)
        elif t == "link_open":
            # markdown-it-py uses attrs for href
            href = ""
            if tok.attrs:
                href = tok.attrs.get("href", "") or ""
            # We'll open bracket and store href on token.meta for close.
            tok.meta = tok.meta or {}
            tok.meta["_href"] = href
            state.push("[")
            if href:
                state.push(href)
        elif t == "link_close":
            # Close as: [url text]
            href = ""
            if tok.meta and "_href" in tok.meta:
                href = tok.meta["_href"] or ""
            # Ensure there is a space before link text if we had url
            # We can't easily know if text exists; but adding a space is safe when url exists.
            if href:
                state.push(" ")
            state.push("]")
        elif t == "image":
            # MediaWiki: [[File:Name|alt=...]] best-effort
            src = ""
            alt = tok.content or ""
            if tok.attrs:
                src = tok.attrs.get("src", "") or ""
            if not src:
                state.warnings.append("Image without src encountered; omitted.")
            else:
                # Use raw src as filename/url. Many wikis allow external image URLs; if not, user can adjust.
                if alt:
                    state.push(f"[[File:{src}|alt={alt}]]")
                else:
                    state.push(f"[[File:{src}]]")
        else:
            # Unknown token: ignore but warn for visibility (best-effort).
            # Avoid noisy warnings for common structural closes.
            if not t.endswith("_close") and not t.endswith("_open"):
                state.warnings.append(f"Unhandled token type: {t}")

        i += 1


# PUBLIC_INTERFACE
def convert(markdown: str) -> Tuple[str, List[str]]:
    """
    Convert Markdown to a MediaWiki-ish wiki markup.

    Supported (best-effort):
    - Headings (1–6)
    - Bold/italic
    - Inline code
    - Fenced code blocks
    - Links, images
    - Unordered/ordered lists (with nesting)
    - Blockquotes (best-effort)
    - Horizontal rules
    - Basic tables (best-effort)

    Important:
    - Content inside code/pre is preserved verbatim.
    - The converter may emit warnings for constructs that are approximated.

    Args:
        markdown: Markdown source text.

    Returns:
        (wiki, warnings)
    """
    md_text = _normalize_newlines(markdown)
    state = _RenderState()

    md = _mk_md()
    try:
        tokens = md.parse(md_text)
    except Exception as e:
        # Fail safe: return original text in <pre> with warning
        return (
            f"{state.mappings.pre_open}\n{md_text}\n{state.mappings.pre_close}\n",
            [f"Markdown parse error; returned input as <pre>: {e}"],
        )

    _render_tokens(tokens, state)
    _close_any_open_inline(state)

    wiki = state.get_text().strip()
    if wiki:
        wiki += "\n"
    return wiki, state.warnings
