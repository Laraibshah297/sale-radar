"""Category filter definitions.

A filter reads its value from one of three places:
  variant - a variant attribute (storage, ram, colour, size, region)
  spec    - the product's specs dict (processor, screen_size, gender, fabric, ...)
  offer   - an offer field (condition)

Each category lists the filter keys it shows (Category.filter_specs).
Import specs from CSV with columns named spec_<key>, e.g. spec_processor.
"""
import re

FILTERS = {
    # ---- variant attributes
    "storage": {"label": "Storage", "source": "variant"},
    "ram": {"label": "RAM", "source": "variant"},
    "colour": {"label": "Colour", "source": "variant"},
    "size": {"label": "Size", "source": "variant"},
    "region": {"label": "PTA / region", "source": "variant"},
    # ---- offer
    "condition": {"label": "Condition", "source": "offer"},
    # ---- tech specs
    "processor": {"label": "Processor", "source": "spec"},
    "screen_size": {"label": "Screen size", "source": "spec"},
    "display": {"label": "Display type", "source": "spec"},
    "refresh_rate": {"label": "Refresh rate", "source": "spec"},
    "network": {"label": "Network", "source": "spec"},
    "battery": {"label": "Battery", "source": "spec"},
    "main_camera": {"label": "Main camera", "source": "spec"},
    "os": {"label": "Operating system", "source": "spec"},
    "gpu": {"label": "Graphics", "source": "spec"},
    "connectivity": {"label": "Connectivity", "source": "spec"},
    "noise_cancelling": {"label": "Noise cancelling", "source": "spec"},
    "water_resistance": {"label": "Water resistance", "source": "spec"},
    "capacity": {"label": "Capacity", "source": "spec"},
    "output_power": {"label": "Output power", "source": "spec"},
    "port": {"label": "Port", "source": "spec"},
    "resolution": {"label": "Resolution", "source": "spec"},
    "smart_tv": {"label": "Smart TV", "source": "spec"},
    "tonnage": {"label": "Tonnage", "source": "spec"},
    "inverter": {"label": "Inverter", "source": "spec"},
    "energy_rating": {"label": "Energy rating", "source": "spec"},
    "type": {"label": "Type", "source": "spec"},
    # ---- fashion / beauty specs
    "gender": {"label": "For", "source": "spec"},
    "fit": {"label": "Fit", "source": "spec"},
    "fabric": {"label": "Fabric", "source": "spec"},
    "pieces": {"label": "Pieces", "source": "spec"},
    "sleeve": {"label": "Sleeve", "source": "spec"},
    "season": {"label": "Season", "source": "spec"},
    "shoe_type": {"label": "Shoe type", "source": "spec"},
    "closure": {"label": "Closure", "source": "spec"},
    "skin_type": {"label": "Skin type", "source": "spec"},
    "volume": {"label": "Volume", "source": "spec"},
}

# Category presets: (group, name, slug, filter keys)
CATEGORY_PRESETS = [
    ("Electronics", "Mobile Phones", "mobile-phones",
     ["storage", "ram", "region", "network", "screen_size", "refresh_rate", "battery", "main_camera", "processor", "condition"]),
    ("Electronics", "Laptops", "laptops",
     ["processor", "ram", "storage", "screen_size", "gpu", "display", "os", "condition"]),
    ("Electronics", "Tablets", "tablets",
     ["storage", "ram", "screen_size", "connectivity", "os", "condition"]),
    ("Electronics", "Smartwatches", "smartwatches",
     ["screen_size", "display", "water_resistance", "connectivity", "colour", "condition"]),
    ("Electronics", "Earbuds & Headphones", "audio",
     ["type", "noise_cancelling", "connectivity", "water_resistance", "colour", "condition"]),
    ("Electronics", "Power Banks & Chargers", "power",
     ["type", "capacity", "output_power", "port"]),
    ("Electronics", "TVs", "tvs",
     ["screen_size", "resolution", "display", "smart_tv", "refresh_rate", "condition"]),
    ("Home Appliances", "Air Conditioners", "air-conditioners",
     ["tonnage", "inverter", "energy_rating", "type"]),
    ("Fashion", "Men's Clothing", "mens-clothing",
     ["size", "colour", "type", "fit", "fabric", "sleeve", "season"]),
    ("Fashion", "Women's Clothing", "womens-clothing",
     ["size", "colour", "type", "pieces", "fabric", "season"]),
    ("Fashion", "Unstitched Fabric", "unstitched",
     ["pieces", "fabric", "season", "colour", "gender"]),
    ("Fashion", "Shoes", "shoes",
     ["size", "gender", "shoe_type", "colour", "closure"]),
    ("Beauty", "Beauty & Personal Care", "beauty",
     ["type", "skin_type", "volume", "gender"]),
]

GROUP_ORDER = ["Electronics", "Home Appliances", "Fashion", "Beauty", "Other"]

_CLOTH = ["xxs", "xs", "s", "m", "l", "xl", "xxl", "2xl", "xxxl", "3xl", "4xl", "free size"]


def value_sort_key(key: str, value: str):
    """Sort sizes and numbers sensibly: XS < S < M ... and 39 < 40, 6 < 6.5."""
    v = str(value).strip().lower()
    if key == "size":
        if v in _CLOTH:
            return (0, _CLOTH.index(v), v)
        m = re.match(r"^(uk|eu|us)?\s*(\d+(?:\.\d+)?)", v)
        if m:
            return (1, m.group(1) or "", float(m.group(2)))
    m = re.match(r"^(\d+(?:\.\d+)?)", v)
    if m:
        return (2, float(m.group(1)), v)
    return (3, 0, v)


def filter_label(key: str) -> str:
    return FILTERS.get(key, {}).get("label", key.replace("_", " ").title())


def filter_source(key: str) -> str:
    return FILTERS.get(key, {}).get("source", "spec")


def normalise_spec_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", k.strip().lower()).strip("_")
