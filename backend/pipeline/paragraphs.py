"""Turn extracted text (PDF lines or HTML blocks) into numbered paragraphs.

The verifier later matches LLM quotes against this text, so only whitespace is ever changed here;
wording, numbering and punctuation are kept exactly as in the source."""
import re

from api.schemas import Paragraph

_FOOTER = re.compile(r"^Page\s+\d+(\s+of\s+\d+)?$", re.I)
# "2." "2.1." "2.1.1." or dotted without a trailing dot ("2.1"). Plain "10 years" must not match.
_TOP = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*\.|\d{1,2}(?:\.\d{1,2})+)(?=\s|$)")
_SUB = re.compile(r"^\(([a-z]{1,4}|[A-Z]|\d{1,2})\)(?=\s|$)")
# Letter-head structure that always starts a new block
_STRUCT = re.compile(r"^(?:Dear\b|To,?$|Yours\b|Subject\s*:|CIRCULAR$|Sir\b|Madam\b)")
_TERMINAL = re.compile(r"""(?:[.:;?)”"]|[;,]\s*(?:and|or))$""")
_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"]


def _clean(s: str) -> str:
    return " ".join(s.split())  # also folds non-breaking spaces


def _sub_successor(label: str, last: str | None) -> bool:
    if label in ("a", "A", "i", "1"):  # a new series starts
        return True
    if last is None:
        return False
    nxt = set()
    if len(last) == 1 and not last.isdigit():
        nxt.add(chr(ord(last) + 1))
    if last in _ROMAN and _ROMAN.index(last) + 1 < len(_ROMAN):
        nxt.add(_ROMAN[_ROMAN.index(last) + 1])
    if last.isdigit():
        nxt.add(str(int(last) + 1))
    return label in nxt


class _State:
    top = 0  # number of the current top-level paragraph
    child = 0  # last "top.child" seen under it
    sub: str | None = None  # last "(a)"-style label


def _starts_new(line: str, prev: str, st: _State) -> bool:
    if _STRUCT.match(line):
        return True
    terminal = bool(_TERMINAL.search(prev))
    m = _TOP.match(line)
    if m:
        parts = m.group(1).rstrip(".").split(".")
        top = int(parts[0])
        child = int(parts[1]) if len(parts) > 1 else None
        if child is None:
            # sequential, or a restart at 1 (e.g. body numbering after a numbered address list)
            return terminal or top == st.top + 1 or top == 1
        return terminal or (top == st.top and child == st.child + 1)
    s = _SUB.match(line)
    if s:
        return terminal or _sub_successor(s.group(1), st.sub)
    return False  # unnumbered lines continue the current paragraph


def _update_state(line: str, st: _State) -> None:
    m = _TOP.match(line)
    if m:
        parts = m.group(1).rstrip(".").split(".")
        st.top = int(parts[0])
        st.child = int(parts[1]) if len(parts) > 1 else 0
        st.sub = None
        return
    s = _SUB.match(line)
    if s:
        st.sub = s.group(1)


def split_text(text: str) -> list[Paragraph]:
    """PDF-style text: wrapped lines, page footers, numbering at line starts."""
    st = _State()
    blocks: list[str] = []
    prev = ""
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            prev = ""
            continue
        if _FOOTER.match(line):
            continue
        if not blocks or not prev or _starts_new(line, prev, st):
            blocks.append(line)
            _update_state(line, st)
        elif blocks[-1].endswith("-") and re.search(r"[A-Za-z]-$", blocks[-1]):
            blocks[-1] += line  # "SWAGAT-" + "FI": hyphenated line break, no space
        else:
            blocks[-1] += " " + line
        prev = line
    return assign_ids(blocks)


def assign_ids(blocks: list[str]) -> list[Paragraph]:
    """Id = the paragraph's own numbering; sub-items get their parent's prefix ("3.1(a)") so ids stay unique."""
    out: list[Paragraph] = []
    seen: set[str] = set()
    parent = ""
    for i, text in enumerate(b for b in (_clean(b) for b in blocks) if b):
        m, s = _TOP.match(text), _SUB.match(text)
        if m:
            pid = parent = m.group(1).rstrip(".")
        elif s:
            pid = f"{parent}({s.group(1)})"
        else:
            pid = f"p{i + 1}"
        base, k = pid, 2
        while pid in seen:
            pid = f"{base}-{k}"
            k += 1
        seen.add(pid)
        out.append(Paragraph(id=pid, text=text))
    return out
