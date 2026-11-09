import re
import unicodedata
from opencc import OpenCC


_to_simplified = OpenCC("t2s")


def _normalize(text):
    return _to_simplified.convert(unicodedata.normalize("NFKC", text)).casefold()


def title_matches(title, keyword):
    """Require every search term in the title, treating simplified and traditional text alike."""
    title = _normalize(title)
    terms = _normalize(keyword).split()
    return all(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", title)
               if term.isascii() and re.search(r"[a-z0-9]", term) else term in title
               for term in terms)
