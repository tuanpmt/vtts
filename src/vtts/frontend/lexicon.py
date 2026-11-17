"""Vietnamese lookup tables for text normalization (Northern readings).

The data lives in lexicons/vi/*.tsv (one `key<TAB>reading` per line) so it can be reviewed and
extended without touching code; see docs/frontend/pronunciation-rules.md. The C tables for the
device front-end are generated from these dictionaries (runtime/tools/gen_text_tables.py).
"""

from vtts.frontend.lexicons import load_table

LETTER_NAMES: dict[str, str] = load_table("vi", "letters")
LOANWORDS: dict[str, str] = load_table("vi", "loanwords")
# Applied case-sensitively, longest key first, only at word boundaries.
ABBREVIATIONS: dict[str, str] = load_table("vi", "abbreviations")
UNITS: dict[str, str] = load_table("vi", "units")
CURRENCIES: dict[str, str] = load_table("vi", "currencies")
SYMBOLS: dict[str, str] = load_table("vi", "symbols")
