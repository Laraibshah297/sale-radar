"""Pakistan-specific e-commerce intelligence engines:
1. Bank Card & Digital Wallet Discount Stacking Optimizer (HBL, Meezan, Alfalah, SCB, UBL, NayaPay, JazzCash)
2. BNPL & Shariah/Zero-Markup Installment Calculator (BaadMay, KalPay, QistBazaar, Bank EMI)
3. Official FBR DIRBS PTA Smartphone Tax & Landed Cost Calculator (Passport vs CNIC)
4. AI Buy-Now vs Wait Price Verdict Signal
5. Smart Budget & Use-Case Shopping Concierge
"""
from decimal import Decimal

# ---- 1. Bank Cards & Digital Wallets in Pakistan
BANK_CARDS = {
    "hbl": {
        "slug": "hbl",
        "name": "HBL Credit & Debit Cards",
        "short": "HBL 10% Off",
        "pct": 10,
        "max_cap": Decimal("5000"),
        "min_spend": Decimal("5000"),
        "type": "Credit / Debit Card",
        "note": "10% instant discount up to Rs 5,000 on partner tech & fashion stores",
    },
    "alfalah": {
        "slug": "alfalah",
        "name": "Bank Alfalah / Alfa App",
        "short": "Alfalah 15% Off",
        "pct": 15,
        "max_cap": Decimal("7500"),
        "min_spend": Decimal("10000"),
        "type": "Credit / Debit / Alfa Wallet",
        "note": "15% off up to Rs 7,500 + 0% SBS installment eligibility",
    },
    "meezan": {
        "slug": "meezan",
        "name": "Meezan Bank Islamic Debit",
        "short": "Meezan 12% Off",
        "pct": 12,
        "max_cap": Decimal("4000"),
        "min_spend": Decimal("3000"),
        "type": "Islamic Debit Card",
        "note": "12% Shariah-compliant discount up to Rs 4,000 on partner stores",
    },
    "scb": {
        "slug": "scb",
        "name": "Standard Chartered (SCB)",
        "short": "SCB 10% Off",
        "pct": 10,
        "max_cap": Decimal("6000"),
        "min_spend": Decimal("15000"),
        "type": "Credit Card",
        "note": "10% off up to Rs 6,000 on smartphones, laptops & appliances",
    },
    "ubl": {
        "slug": "ubl",
        "name": "UBL Visa / Mastercard",
        "short": "UBL 10% Off",
        "pct": 10,
        "max_cap": Decimal("3500"),
        "min_spend": Decimal("4000"),
        "type": "Credit / Debit Card",
        "note": "10% off up to Rs 3,500 on lifestyle, footwear & electronics",
    },
    "nayapay": {
        "slug": "nayapay",
        "name": "NayaPay / SadaPay Visa",
        "short": "NayaPay 5% Off",
        "pct": 5,
        "max_cap": Decimal("1500"),
        "min_spend": Decimal("1500"),
        "type": "Free Virtual / Debit Card",
        "note": "5% instant discount up to Rs 1,500 — no credit card required",
    },
    "jazzcash": {
        "slug": "jazzcash",
        "name": "JazzCash / Easypaisa Wallet",
        "short": "JazzCash 8% Off",
        "pct": 8,
        "max_cap": Decimal("2000"),
        "min_spend": Decimal("2000"),
        "type": "Mobile Wallet / QR",
        "note": "8% instant wallet cashback up to Rs 2,000 on online checkout",
    },
}

PROMO_PCTS = {
    "RADAR5": 5,
    "EIDSALE": 8,
    "AZADI10": 10,
    "BLESSED10": 10,
    "BLESSED15": 12,
    "TECH2500": 0,  # flat Rs 2500
}


def promo_savings_for(price: Decimal, promo_code: str | None) -> Decimal:
    if not promo_code:
        return Decimal("0")
    code = promo_code.strip().upper()
    if code == "TECH2500" and price >= Decimal("25000"):
        return Decimal("2500")
    pct = PROMO_PCTS.get(code, 5)
    raw = (price * Decimal(pct) / Decimal("100")).quantize(Decimal("1"))
    return min(raw, Decimal("4000"))


def net_price_with_card(offer, card_slug: str | None = None) -> dict:
    """Calculates effective checkout price after promo voucher + bank card/wallet discount + shipping."""
    base = Decimal(offer.price)
    ship = Decimal(offer.shipping_cost) if offer.shipping_cost is not None else Decimal("0")
    promo_disc = promo_savings_for(base, getattr(offer, "promo_code", None))
    after_promo = max(Decimal("0"), base - promo_disc)

    card = BANK_CARDS.get((card_slug or "").lower().strip())
    partners_raw = getattr(offer.retailer, "bank_partners", None) or ""
    partner_set = {x.strip().lower() for x in partners_raw.split(",") if x.strip()}

    bank_disc = Decimal("0")
    card_applied = False
    if card and card["slug"] in partner_set and after_promo >= card["min_spend"]:
        raw_bank = (after_promo * Decimal(card["pct"]) / Decimal("100")).quantize(Decimal("1"))
        bank_disc = min(raw_bank, card["max_cap"])
        card_applied = True

    net_item = max(Decimal("0"), after_promo - bank_disc)
    net_delivered = (net_item + ship) if offer.shipping_cost is not None else None
    total_saved = promo_disc + bank_disc
    return {
        "card": card,
        "card_applied": card_applied,
        "promo_discount": promo_disc,
        "bank_discount": bank_disc,
        "total_discount": total_saved,
        "net_item_price": net_item,
        "net_delivered_price": net_delivered,
        "partner_cards": [BANK_CARDS[c] for c in partner_set if c in BANK_CARDS],
    }


# ---- 2. BNPL & Installment Plans (Pakistan)
def calculate_installments(price_pkr: Decimal | float | int, category_slug: str | None = None) -> list[dict]:
    """Returns realistic Pakistani BNPL (Debit/CNIC) and Bank Credit Card EMI options."""
    p = Decimal(str(price_pkr))
    if p <= 0:
        return []
    plans = []
    # 1. BaadMay 3-Month Debit Card Split (huge for fashion, shoes, beauty, earbuds, mid-range phones <= 100k)
    if p <= Decimal("120000"):
        total_baadmay = (p * Decimal("1.04")).quantize(Decimal("1"))  # small platform service fee
        monthly = (total_baadmay / Decimal("3")).quantize(Decimal("1"))
        plans.append({
            "provider": "BaadMay",
            "badge": "No Credit Card Needed",
            "type": "Debit Card 3x Split",
            "months": 3,
            "upfront": monthly,
            "monthly": monthly,
            "total": total_baadmay,
            "markup_note": "Pay 1/3 today via any Visa/Mastercard Debit Card",
            "shariah": False,
        })
    # 2. KalPay Shariah-Compliant Halal 3-Month Split
    if p <= Decimal("150000"):
        total_kalpay = (p * Decimal("1.03")).quantize(Decimal("1"))
        monthly_k = (total_kalpay / Decimal("3")).quantize(Decimal("1"))
        plans.append({
            "provider": "KalPay",
            "badge": "Shariah Compliant",
            "type": "Halal 3-Month Split",
            "months": 3,
            "upfront": monthly_k,
            "monthly": monthly_k,
            "total": total_kalpay,
            "markup_note": "Zero late-interest Islamic Musawamah structure",
            "shariah": True,
        })
    # 3. Bank Alfalah / HBL 0% Markup 6-Month Credit Card EMI (for orders >= Rs 10,000)
    if p >= Decimal("10000"):
        proc_fee = min((p * Decimal("0.025")).quantize(Decimal("1")), Decimal("3000"))
        monthly_6 = (p / Decimal("6")).quantize(Decimal("1"))
        plans.append({
            "provider": "AlfaMall / Bank SBS",
            "badge": "0% Markup",
            "type": "Credit Card 6-Month EMI",
            "months": 6,
            "upfront": proc_fee,
            "monthly": monthly_6,
            "total": p + proc_fee,
            "markup_note": f"0% interest + one-time Rs {int(proc_fee):,} bank processing fee",
            "shariah": False,
        })
    # 4. QistBazaar / 12-Month CNIC Easy Installments (for phones, laptops, TVs, ACs >= Rs 20,000)
    if p >= Decimal("20000") and category_slug in (
        None, "", "mobile-phones", "laptops", "tablets", "tvs", "air-conditioners"
    ):
        down = (p * Decimal("0.20")).quantize(Decimal("1"))
        financed = (p - down) * Decimal("1.22")
        monthly_12 = (financed / Decimal("12")).quantize(Decimal("1"))
        plans.append({
            "provider": "QistBazaar",
            "badge": "CNIC Only (Unbanked)",
            "type": "12-Month Easy Qist",
            "months": 12,
            "upfront": down,
            "monthly": monthly_12,
            "total": (down + monthly_12 * 12).quantize(Decimal("1")),
            "markup_note": f"20% advance (Rs {int(down):,}) on CNIC verification, no bank card needed",
            "shariah": True,
        })
    return plans


# ---- 3. Official FBR DIRBS PTA Smartphone Tax Calculator
PTA_DEVICE_PRESETS = [
    {"slug": "iphone-16-pro-max", "name": "Apple iPhone 16 Pro Max", "usd": 1199, "passport": 152500, "cnic": 183500},
    {"slug": "iphone-16", "name": "Apple iPhone 16 (128GB)", "usd": 799, "passport": 128000, "cnic": 154500},
    {"slug": "iphone-15-pro-max", "name": "Apple iPhone 15 Pro Max", "usd": 999, "passport": 146500, "cnic": 176800},
    {"slug": "iphone-15", "name": "Apple iPhone 15 (128GB)", "usd": 699, "passport": 107500, "cnic": 130800},
    {"slug": "iphone-14", "name": "Apple iPhone 14 (128GB)", "usd": 599, "passport": 94500, "cnic": 116000},
    {"slug": "iphone-13", "name": "Apple iPhone 13 (128GB)", "usd": 499, "passport": 72500, "cnic": 89500},
    {"slug": "iphone-12", "name": "Apple iPhone 12", "usd": 369, "passport": 56000, "cnic": 69500},
    {"slug": "galaxy-s24-ultra", "name": "Samsung Galaxy S24 Ultra", "usd": 1099, "passport": 142000, "cnic": 171500},
    {"slug": "galaxy-s24", "name": "Samsung Galaxy S24 5G", "usd": 749, "passport": 114000, "cnic": 138000},
    {"slug": "galaxy-a55", "name": "Samsung Galaxy A55 5G", "usd": 379, "passport": 48500, "cnic": 59800},
    {"slug": "pixel-8-pro", "name": "Google Pixel 8 Pro", "usd": 699, "passport": 104000, "cnic": 127500},
    {"slug": "pixel-7-pro", "name": "Google Pixel 7 Pro", "usd": 399, "passport": 54500, "cnic": 67800},
    {"slug": "oneplus-12", "name": "OnePlus 12 5G", "usd": 699, "passport": 98000, "cnic": 119500},
]


def estimate_pta_tax(usd_value: float | None = None, title: str = "") -> dict:
    """Calculates FBR DIRBS PTA Registration Tax on Passport vs CNIC."""
    t_low = (title or "").lower()
    for preset in PTA_DEVICE_PRESETS:
        key_words = preset["slug"].replace("-", " ")
        if key_words in t_low:
            return {
                "matched_preset": preset["name"],
                "usd_value": preset["usd"],
                "passport_tax": Decimal(str(preset["passport"])),
                "cnic_tax": Decimal(str(preset["cnic"])),
                "passport_savings": Decimal(str(preset["cnic"] - preset["passport"])),
                "slab": _pta_slab_label(preset["usd"]),
            }
    usd = float(usd_value if usd_value is not None else 350.0)
    if usd <= 30:
        pass_tax, cnic_tax = 550, 650
    elif usd <= 100:
        pass_tax, cnic_tax = 4300, 5200
    elif usd <= 200:
        pass_tax, cnic_tax = 13800, 16900
    elif usd <= 350:
        pass_tax, cnic_tax = int(26500 + (usd - 200) * 95), int(32800 + (usd - 200) * 115)
    elif usd <= 500:
        pass_tax, cnic_tax = int(52000 + (usd - 350) * 145), int(64000 + (usd - 350) * 175)
    elif usd <= 700:
        pass_tax, cnic_tax = int(86000 + (usd - 500) * 120), int(105000 + (usd - 500) * 145)
    else:
        pass_tax, cnic_tax = int(122000 + min(usd - 700, 600) * 62), int(148000 + min(usd - 700, 600) * 74)
    pass_tax = int(round(pass_tax / 100) * 100)
    cnic_tax = int(round(cnic_tax / 100) * 100)
    return {
        "matched_preset": None,
        "usd_value": round(usd, 2),
        "passport_tax": Decimal(str(pass_tax)),
        "cnic_tax": Decimal(str(cnic_tax)),
        "passport_savings": Decimal(str(cnic_tax - pass_tax)),
        "slab": _pta_slab_label(usd),
    }


def _pta_slab_label(usd: float) -> str:
    if usd <= 30:
        return "Tier 1 (Up to $30)"
    if usd <= 100:
        return "Tier 2 ($30 – $100)"
    if usd <= 200:
        return "Tier 3 ($100 – $200)"
    if usd <= 350:
        return "Tier 4 ($200 – $350)"
    if usd <= 500:
        return "Tier 5 ($350 – $500)"
    if usd <= 700:
        return "Tier 6 ($500 – $700)"
    return "Tier 7 (Above $700 Flagship)"


# ---- 4. AI Buy-Now vs Wait Price Verdict
def ai_buy_verdict(current_low: Decimal | None, deal: dict | None, stores_count: int = 1) -> dict | None:
    if current_low is None:
        return None
    if not deal:
        return {
            "verdict": "FAIR MARKET PRICE",
            "icon": "🟡",
            "tone": "blue",
            "headline": "Compare store warranty & apply a bank/wallet card",
            "reason": f"Tracked across {stores_count} verified stores. Select your bank card below to unlock extra checkout savings.",
        }
    drop = float(deal.get("drop_pct", 0.0))
    cur = float(current_low)
    low_30 = float(deal["low"])
    med_30 = float(deal["median"])
    if cur <= low_30 * 1.005 or drop >= 5.0:
        saved = max(0, int(med_30 - cur))
        return {
            "verdict": "STRONG BUY NOW",
            "icon": "🟢",
            "tone": "good",
            "headline": f"At 30-day price floor — Rs {saved:,} below typical market rate",
            "reason": "Historical data shows prices rarely dip lower than this level outside clearance. Lock in this offer before stock runs out.",
        }
    if drop >= 1.5:
        return {
            "verdict": "GOOD TIME TO BUY",
            "icon": "🟢",
            "tone": "good",
            "headline": f"Trading {drop:.1f}% below 30-day median — genuine discount",
            "reason": "Price is verified below the 30-day average. Stack a partner Bank Card or Wallet offer below for maximum savings.",
        }
    if cur > med_30 * 1.03:
        target = int(med_30 // 100 * 100)
        return {
            "verdict": "WAIT / SET PRICE ALERT",
            "icon": "🔴",
            "tone": "bad",
            "headline": f"Currently above 30-day typical price (Rs {int(med_30):,})",
            "reason": f"Retailers raised prices recently. Unless urgent, set a Price Alert for Rs {target:,} or wait for the next campaign.",
        }
    return {
        "verdict": "BUY WITH BANK CARD",
        "icon": "🟡",
        "tone": "blue",
        "headline": "Steady market price — beat the 30-day low using Bank / Wallet discounts",
        "reason": "Organic price is stable near its 30-day median. Applying HBL, Alfalah, Meezan, or JazzCash at checkout drops your net cost below the 30-day low.",
    }
