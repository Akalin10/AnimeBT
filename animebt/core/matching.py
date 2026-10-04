import re
import unicodedata


def title_matches(title, keyword):
    """Require every literal search term in the original title, not site descriptions."""
    title = unicodedata.normalize("NFKC", title).casefold()
    terms = unicodedata.normalize("NFKC", keyword).casefold().split()
    return all(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", title)
               if term.isascii() and re.search(r"[a-z0-9]", term) else term in title
               for term in terms)
