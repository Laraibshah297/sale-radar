"""Text normalisation shared by search, matching and imports."""
import re
import unicodedata

# English / Roman Urdu synonyms. Each group is treated as one word.
SYNONYM_GROUPS = [
    {"mobile", "phone", "cell", "cellphone", "smartphone", "fon", "mobail", "mobiles", "phones"},
    {"laptop", "notebook", "laptops"},
    {"earbuds", "earphones", "airbuds", "buds", "tws", "earbud", "handsfree", "hands-free"},
    {"headphones", "headphone", "headset"},
    {"charger", "adapter", "adaptor"},
    {"smartwatch", "watch", "ghari", "gharee"},
    {"powerbank", "power bank"},
    {"tablet", "tab", "ipad"},
    {"cover", "case", "pouch"},
    {"gb", "gig"},
]
_SYN = {}
for group in SYNONYM_GROUPS:
    for w in group:
        _SYN[w] = group


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).lower()
    s = re.sub(r"(\d)\s*(gb|tb|mah|w|inch|in)\b", r"\1\2", s)  # "256 GB" -> "256gb"
    s = re.sub(r"[^a-z0-9؀-ۿ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compact(s: str | None) -> str:
    """'SM-S931B' and 'sm s931 b' both become 'sms931b' (model numbers)."""
    return re.sub(r"[^a-z0-9]", "", norm(s))


def tokens(s: str | None) -> list[str]:
    return [t for t in norm(s).split(" ") if t]


def synonyms(word: str) -> set[str]:
    return _SYN.get(word, {word})


def slugify(s: str, max_len: int = 120) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")
    return s[:max_len].strip("-") or "item"


def norm_storage(s: str | None) -> str:
    v = compact(s)
    if re.fullmatch(r"\d+", v):
        v += "gb"
    return v


def search_text_for(product) -> str:
    parts = [product.title, product.brand, product.model_number, compact(product.model_number)]
    if product.category:
        parts.append(product.category.name)
    for k, v in (product.specs or {}).items():
        parts.append(f"{k} {v}")
    for v in product.variants:
        parts += [v.storage, v.ram, v.colour, v.size, v.region, v.gtin]
    return norm(" ".join(p for p in parts if p))
