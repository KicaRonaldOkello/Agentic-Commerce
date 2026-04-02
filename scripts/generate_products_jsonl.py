#!/usr/bin/env python3
"""
Generate data/products.jsonl:
  - 1000 phones + 1000 TVs (same uniform schema for one DB)
  - Per category: 40% low / 30% mid / 30% high tier
  - 900 unique listings + 100 duplicate-style rows (~10%) per category
Images: Unsplash (images.unsplash.com) + Picsum (picsum.photos) — frontend-safe HTTPS URLs.

Marketing copy is procedurally blended from Jumia-style patterns (informed by jumia.ug smartphone
category listings and a sample Galaxy A14 PDP): tier-specific tone, brand voice buckets
(Samsung / Apple / Transsion / Xiaomi / BBK / Nokia-Moto / import flagship / budget generic),
and variable “what’s in the box” bullets like marketplace sellers use.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from pathlib import Path
from typing import Any

random.seed(42)

# Curated Unsplash photo IDs — technology / phones / handheld screens
PHONE_UNSPLASH_IDS = [
    "1511707171634-5f897ff02aa9",
    "1510557880182-e9596292e5a3",
    "1574944983730-c0539ebfa532",
    "1556656793-08538906a9f8",
    "1601784555292-f893be77d5a8",
    "1598327105666-5b8121512eae",
    "1585060544812-6b45742d7629",
    "1565849909693-8d3c63736c7e",
    "1610945265060-2906a41d0c90",
    "1592284440920-8a07776921b9",
    "1496188500368-99d5f13e0650",
    "1580910051074-3eb694886b39",
    "1592899677976-141c77768634",
    "1592750475338-74b7b21085ab",
    "1517336714731-e4896a06a744",
    "1563013544-824ae1b704d3",
    "1512941937669-90a1b58e7e9d",
    "1601972602237-8a07776921b9",
    "1523207226338-8f1e0e7a3c0d",
    "1586023492125-27b2c245efd0",
    "1556656793-08538906a9f8",
    "1601784555292-f893be77d5a8",
    "1574944983730-c0539ebfa532",
    "1610945265060-2906a41d0c90",
    "1598327105666-5b8121512eae",
    "1496188500368-99d5f13e0650",
    "1580910051074-3eb694886b39",
    "1511707171634-5f897ff02aa9",
    "1565849909693-8d3c63736c7e",
    "1592284440920-8a07776921b9",
]

# Living room / screen / interior — TV-adjacent hero imagery
TV_UNSPLASH_IDS = [
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1563013544-824ae1b704d3",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1563013544-824ae1b704d3",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1563013544-824ae1b704d3",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1563013544-824ae1b704d3",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
    "1593359676828-14f3a27a8552",
    "1563013544-824ae1b704d3",
    "1513694203230-7191fa18eea8",
    "1555040142-5f888eeecba8",
    "1586023492125-27b2c245efd0",
]


def unsplash_url(photo_id: str, w: int = 800, h: int = 800) -> str:
    return (
        f"https://images.unsplash.com/photo-{photo_id}"
        f"?auto=format&fit=crop&w={w}&h={h}&q=80"
    )


def picsum_url(seed: int, w: int = 800, h: int = 600) -> str:
    """Deterministic Lorem Picsum image (stable id 0–1024)."""
    pid = (seed % 1024) + 1
    return f"https://picsum.photos/id/{pid}/{w}/{h}"


def image_set_for_product(kind: str, idx: int) -> tuple[str, list[str]]:
    if kind == "phone":
        pool = PHONE_UNSPLASH_IDS
    else:
        pool = TV_UNSPLASH_IDS
    a = pool[idx % len(pool)]
    b = pool[(idx + 11) % len(pool)]
    u1 = unsplash_url(a, 800, 800)
    u2 = unsplash_url(b, 1200, 800)
    p1 = picsum_url(idx * 9973 + 101, 800, 800)
    p2 = picsum_url(idx * 7919 + 303, 800, 600)
    return u1, [u1, u2, p1, p2]


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:120]


def tier_for_index(i: int, total: int) -> str:
    low_n = int(total * 0.4)
    mid_n = int(total * 0.3)
    if i < low_n:
        return "low"
    if i < low_n + mid_n:
        return "mid"
    return "high"


PHONE_BRANDS = {
    "low": ["Tecno", "Infinix", "Itel", "Nokia", "Redmi", "Realme", "Syinix", "Vivo"],
    "mid": ["Samsung", "Xiaomi", "Oppo", "Vivo", "Motorola", "Huawei", "Realme", "OnePlus"],
    "high": ["Apple", "Samsung", "Google", "Sony", "Xiaomi", "OnePlus", "Oppo", "Huawei"],
}

TV_BRANDS = {
    "low": ["Bravo", "Vitron", "Syinix", "Sayona", "ARMCO", "Noble", "Crown", "Icon"],
    "mid": ["TCL", "Hisense", "Skyworth", "LG", "Samsung", "Haier", "Panasonic", "Sharp"],
    "high": ["Samsung", "LG", "Sony", "Philips", "TCL", "Hisense", "Panasonic", "Bang Olufsen"],
}

PHONE_SERIES_LOW = ["POP", "Spark", "A", "C", "Go", "Y", "Neo", "Lite"]
PHONE_SERIES_MID = ["Galaxy A", "Redmi Note", "Narzo", "Reno", "Y", "G", "nova", "Edge"]
PHONE_SERIES_HIGH = ["Galaxy S", "Galaxy Z", "iPhone", "Pixel", "Find", "X", "Pro", "Ultra"]

TV_SERIES_LOW = ["Frameless HD", "Digital LED", "Smart HD", "D-LED", "Vision", "Crystal"]
TV_SERIES_MID = ["4K UHD", "QLED", "ULED", "Android TV", "Google TV", "Smart 4K"]
TV_SERIES_HIGH = ["OLED evo", "Neo QLED", "BRAVIA XR", "MASTER Series", "QD-OLED", "8K QLED"]

COLORS = ["Black", "Graphite", "Silver", "Blue", "Green", "Gold", "White", "Violet"]

# ---------------------------------------------------------------------------
# Jumia-style copy (patterns informed by jumia.ug smartphone listings & PDPs)
# ---------------------------------------------------------------------------

PHONE_BRAND_VOICE: dict[str, str] = {}
for b in ["Samsung"]:
    PHONE_BRAND_VOICE[b] = "samsung"
for b in ["Apple"]:
    PHONE_BRAND_VOICE[b] = "apple"
for b in ["Redmi", "Xiaomi"]:
    PHONE_BRAND_VOICE[b] = "xiaomi"
for b in ["Tecno", "Infinix", "Itel"]:
    PHONE_BRAND_VOICE[b] = "transsion"
for b in ["Oppo", "Vivo", "Realme"]:
    PHONE_BRAND_VOICE[b] = "bbk"
for b in ["Nokia", "Motorola"]:
    PHONE_BRAND_VOICE[b] = "hmd_moto"
for b in ["Google", "OnePlus", "Sony", "Huawei"]:
    PHONE_BRAND_VOICE[b] = "global_flagship"


def phone_voice(brand: str) -> str:
    return PHONE_BRAND_VOICE.get(brand, "budget_generic")


def _pick(r: random.Random, items: list[str], n: int) -> list[str]:
    return r.sample(items, min(n, len(items)))


def generate_phone_marketing(
    r: random.Random,
    *,
    brand: str,
    tier: str,
    series: str,
    model_num: str,
    inch: float,
    ram: int,
    rom: int,
    cam: int,
    color: str,
) -> tuple[str, str, list[str], list[str]]:
    """Returns (shortDescription, description, keyFeatures, whatsInTheBox)."""
    voice = phone_voice(brand)
    model = f"{series}{model_num}".strip()
    ctx = {
        "brand": brand,
        "model": model,
        "inch": inch,
        "ram": ram,
        "rom": rom,
        "cam": cam,
        "color": color,
        "tier": tier,
    }

    # --- Short intros: tier × voice (Jumia listing tone)
    low_short = {
        "samsung": (
            "{brand} {model} — {inch}\" display, {ram}GB RAM + {rom}GB ROM, {cam}MP camera, big battery, Dual SIM — "
            "everyday Android phone with trusted after-sales network."
        ),
        "transsion": (
            "{brand} {model} Smartphone – {inch}\" display, up to {ram}GB RAM, {rom}GB ROM, {cam}MP camera, "
            "5000mAh-class battery, Dual SIM, 4G — built for big-screen entertainment on a budget."
        ),
        "xiaomi": (
            "{brand} {model} {inch}\" — {ram}GB RAM, {rom}GB ROM, {cam}MP, fast charging — "
            "value-packed specs popular on Jumia for students and families."
        ),
        "budget_generic": (
            "{brand} {model} 4G — {inch}\" HD+ screen, {ram}GB+{rom}GB, {cam}MP, 5000mAh, Dual SIM "
            "(bundle-ready: check listing for free screen protector / cover where offered)."
        ),
        "apple": (
            "{brand} {model} — compact iOS experience, {rom}GB storage, premium materials — "
            "refurbished and new-in-box listings vary by seller."
        ),
        "bbk": (
            "{brand} {model} — {inch}\" eye-care display, {ram}GB RAM, {rom}GB ROM, {cam}MP portrait camera, "
            "fast unlock — mid-budget photography focus."
        ),
        "hmd_moto": (
            "{brand} {model} — clean Android feel, {inch}\" panel, {ram}GB/{rom}GB, {cam}MP — "
            "practical dual-SIM daily driver."
        ),
        "global_flagship": (
            "{brand} {model} — import/flagship tier; {rom}GB storage, pro optics — verify warranty with seller."
        ),
    }
    mid_short = {
        "samsung": (
            "{brand} {model} — {inch}\" FHD+ smooth display, {ram}GB RAM, {rom}GB ROM, {cam}MP multi-camera, "
            "5G on supported SKUs — Galaxy A-series balance: camera, battery, One UI."
        ),
        "xiaomi": (
            "{brand} {model} — {inch}\" display, {ram}GB RAM, {rom}GB ROM, {cam}MP, Android with MIUI/HyperOS — "
            "segment-leading fast charge and stereo on select trims."
        ),
        "transsion": (
            "{brand} {model} — {inch}\" bright display, 16({ram}+{ram})GB-style extended RAM options on some SKUs, "
            "{cam}MP AI camera, 45W–5200mAh-class endurance — Spark/Camon-class Jumia favourites."
        ),
        "bbk": (
            "{brand} {model} — {inch}\" AMOLED on select models, {ram}GB RAM, {rom}GB ROM, {cam}MP, "
            "65W–80W fast charging story where applicable."
        ),
        "apple": (
            "{brand} {model} — Super Retina class display, {ram}GB RAM, {rom}GB, cinematic video — "
            "premium resale value; check single vs dual SIM listing."
        ),
        "hmd_moto": (
            "{brand} {model} — near-stock Android, {inch}\", {ram}GB+{rom}GB, {cam}MP — "
            "Moto G / Nokia X-style reliability."
        ),
        "global_flagship": (
            "{brand} {model} — flagship processor tier, {rom}GB, {cam}MP pro camera — "
            "for buyers who want max performance per shilling."
        ),
        "budget_generic": (
            "{brand} {model} — {inch}\" {ram}GB+{rom}GB, {cam}MP, gaming-friendly refresh on select SKUs."
        ),
    }
    high_short = {
        "samsung": (
            "{brand} {model} — {inch}\" Dynamic AMOLED 2X class story, {ram}GB RAM, up to {rom}GB, {cam}MP pro-grade camera, "
            "IP68, wireless charging — Galaxy S/Ultra territory."
        ),
        "apple": (
            "{brand} {model} — Pro/Max titanium or stainless build, {rom}GB, Action button on newer gens, "
            "48MP–200MP-class main sensor story by generation — iOS flagship."
        ),
        "xiaomi": (
            "{brand} {model} — Leica/partnership-tier imaging on select lines, {inch}\" LTPO, {ram}GB+{rom}GB, "
            "120W fast charge on supported models."
        ),
        "transsion": (
            "{brand} {model} — Phantom/Camon flagship story: periscope or 108MP-class sensors, curved AMOLED, "
            "AI portraits — Transsion’s answer to premium imports."
        ),
        "bbk": (
            "{brand} {model} — Find/Reno/Pro flagship optics, MariSilicon-style processing story, "
            "{ram}GB+{rom}GB, ceramic/glass builds."
        ),
        "global_flagship": (
            "{brand} {model} — true flagship: computational photography, IP rating, wireless, "
            "multi-year OS promise where brand applies."
        ),
        "hmd_moto": (
            "{brand} {model} — edge+ / razr-class story on select listings; premium Android with clean UI."
        ),
        "budget_generic": (
            "{brand} {model} — maxed-out specs for the price: {cam}MP, {rom}GB, gamer RGB styling on some SKUs."
        ),
    }

    if tier == "low":
        short_tmpl = low_short.get(voice, low_short["budget_generic"])
    elif tier == "mid":
        short_tmpl = mid_short.get(voice, mid_short["budget_generic"])
    else:
        short_tmpl = high_short.get(voice, high_short["budget_generic"])
    short = short_tmpl.format(**ctx)

    # --- Long description paragraphs (Jumia PDP + listing mash-up)
    low_para = [
        "Full screen brings wide vision: higher screen ratio spreads the picture edge-to-edge for immersive viewing of shorts, football highlights, and church streams.",
        "Love your home—get closer to family with one reliable handset: dual SIM keeps work and personal lines separate without carrying two phones.",
        "HD+ and waterdrop / punch-hole styles (varies by SKU) keep everyday content sharp enough for WhatsApp, TikTok, and mobile money apps.",
        "Big {cam}MP main sensor story + auxiliary lenses on supported models; daylight shots pop for social, night mode honesty varies by tier.",
        "5000mAh-class batteries and 10W–33W charging claims (check adapter in box) match how Jumia shoppers compare Tecno, Infinix, Redmi, and Samsung A-series.",
        "Comes with Dual SIM (nano), microSD on many entry SKUs, FM radio and 3.5mm jack where still offered—small features that beat some expensive thin phones.",
        "Order confidently: confirm whether adapter, earphones, or free glass protector/cover are included—listings differ by seller like on Jumia Uganda / Nigeria.",
    ]
    mid_para = [
        "Balances performance and price: smoother scrolling (90–120Hz on many SKUs), stronger GPUs for CoD Mobile / PUBG on medium settings, and faster UFS storage than entry lines.",
        "Camera systems lean on AI scene boost and ultrawide for group photos; 50–108MP main sensors are common in this band—pixel-binning for cleaner low light.",
        "Fast charging (18W–67W depending on brand) changes daily rhythm: top up during lunch, not overnight—verify cable and brick in the box.",
        "5G or advanced 4G aggregation on supported models; check your carrier bands before buying import SKUs.",
        "Builds mix glass fronts with composite frames; IP ratings appear on select mid phones (e.g. splash resistance)—read the fine print.",
        "Software: One UI, HyperOS/MIUI, ColorOS, Funtouch—each has different bloat and update cadence; mid-range is where Android version longevity starts to matter.",
    ]
    high_para = [
        "Flagship tier: premium materials (titanium, ceramic shield, Gorilla Victus), brighter outdoor-readable panels, and class-leading video stabilization for creators.",
        "Optical zoom / periscope or 48–200MP main sensors with large sensors—night photography and portrait falloff clearly outclass budget 64MP marketing numbers.",
        "Wireless charging, reverse wireless, UWB or satellite SOS (brand dependent), and multi-year security updates define total cost of ownership—not just day-one price.",
        "Gaming sustained performance: vapor chambers and throttling behaviour matter more than benchmark peaks; this tier is for buyers who keep phones 3+ years.",
        "Ecosystem hooks: seamless buds/watch/laptop handoff on Apple/Samsung/Huawei stacks—worth the premium if you already own accessories.",
        "Resale liquidity is highest here; grey-import vs official distributor affects warranty—Jumia-style multi-seller listings make that explicit.",
    ]

    voice_para = {
        "samsung": [
            "{brand} combines streamlined design with classic colours. Refined curves make it comfortable to hold and easy to navigate one-handed.",
            "Expand your view on the {inch}\" Infinity-V / Infinity-O style display—HD+ or FHD+ depending on model—so everyday content looks sharp, crisp, and clear.",
            "Multi-camera layouts add perspective: ultrawide for tight spaces, macro for detail, depth for portraits—similar storytelling to Galaxy A-series PDP copy on Jumia.",
            "One UI layers useful extras (Secure Folder, Game Launcher, Knox basics on supported devices) while staying familiar to upgraders from older Galaxies.",
        ],
        "apple": [
            "Designed for iOS buyers who prioritise video, iMessage, and long software support—colour and storage trims vary; verify if listing is single or dual eSIM/SIM.",
            "Ceramic Shield front (generation dependent), surgical steel or titanium frames on Pro lines, and Action button on latest Pro models—check exact generation in the title.",
            "Cameras lean on computational photography: Night mode, Cinematic mode, ProRAW/ProRes on supported SKUs—ideal for content creators already in the Apple stack.",
        ],
        "xiaomi": [
            "Redmi / Xiaomi listings on Jumia stress big batteries, 33W–120W fast charge, and Android version in the title (e.g. Android 14/15)—HyperOS or MIUI features vary by region.",
            "Stereo speakers, IR blaster on many models, and expandable storage on select lines remain fan-favourite differentiators vs slim flagships.",
        ],
        "transsion": [
            "Tecno / Infinix / Itel copy often highlights AI cameras, ‘extended RAM’ (8+8GB style), 5000–6000mAh cells, and bright displays for outdoor markets.",
            "Spark and Camon families push 45W charging, AMOLED on slimmer bodies, and aggressive portrait beautification tuned for regional preferences.",
            "IP54/IP65 splash claims appear on newer Itel City / A-series lines—confirm rating on your exact SKU before relying on it near water.",
        ],
        "bbk": [
            "Oppo / Vivo / Realme emphasise portrait algorithms, eye-comfort certified displays, and 65W+ SuperVOOC-style charging on mid-high trims.",
            "ColorOS / Funtouch / realme UI share roots—expect heavy feature packs and gaming modes; update policies differ by series.",
        ],
        "hmd_moto": [
            "Nokia / Motorola lean on cleaner Android, promised security updates on many models, and practical dual-SIM slots—less gimmick, more predictable software.",
            "Moto Actions and Nokia durability stories echo Jumia listings that mention ‘stock Android’ as a selling point next to Chinese-skinned rivals.",
        ],
        "global_flagship": [
            "Pixel leans computational; Xperia leans creator/pro video; OnePlus leans fast charging and OxygenOS; Huawei leans camera hardware where GMS availability allows—each voice differs.",
            "Import buyers compare band support, warranty, and charger type (Type-C PD vs proprietary) exactly like cross-border Jumia offers.",
        ],
        "budget_generic": [
            "Generic and white-label listings often bundle ‘free screen protector + cover + earphones’ and shout Global Version / Face Unlock / waterdrop HD+ screen.",
            "Specs tables may list ‘8(4+4)GB’ extended RAM, dual cameras, and 5000mAh—read reviews for real-world speed and camera quality.",
        ],
    }

    body_parts: list[str] = []
    if tier == "low":
        body_parts.extend(_pick(r, low_para, r.randint(3, 5)))
    elif tier == "mid":
        body_parts.extend(_pick(r, mid_para, r.randint(3, 5)))
    else:
        body_parts.extend(_pick(r, high_para, r.randint(3, 5)))
    body_parts.extend(_pick(r, voice_para.get(voice, voice_para["budget_generic"]), min(3, len(voice_para.get(voice, voice_para["budget_generic"])))))

    desc = " ".join(p.format(**ctx) if "{" in p else p for p in body_parts)

    # --- Key features: Jumia bullet style, tier-specific
    kf_low_pool = [
        f'{inch}" HD+ / waterdrop or punch-hole display — wide view for video and reading',
        "Dual SIM (nano) — separate work and personal lines",
        f"{cam}MP main camera + depth/macro where listed — daylight social shots",
        f"{ram}GB RAM + {rom}GB ROM — expandable storage on many SKUs (dedicated microSD slot)",
        "5000mAh-class battery — all-day use for typical chat + video users",
        "USB Type-C charging — confirm wattage and whether adapter ships in box",
        "Fingerprint (side/rear) or face unlock — varies by model",
        "FM radio & 3.5mm jack on select entry phones — still requested in local markets",
    ]
    kf_mid_pool = [
        f'{inch}" FHD+ display — 90–120Hz on many listings (check exact model)',
        f"{ram}GB RAM + {rom}GB UFS storage — smoother multitasking than 64GB eMMC entry phones",
        f"{cam}MP triple/quad camera — ultrawide + macro story as on Jumia spec sheets",
        "Fast charging 18W–67W (model dependent) — less time tethered to the wall",
        "5G or Cat-12+ 4G — confirm bands for your carrier",
        "Stereo speakers on select models — better TikTok/YouTube than single bottom fire",
        "NFC on supported SKUs — Google Pay where banks support",
    ]
    kf_high_pool = [
        f'{inch}" flagship-grade OLED/LTPO panel — high brightness outdoor use',
        f"{ram}GB RAM + up to {rom}GB storage — heavy games and 4K video",
        f"{cam}MP pro camera system — optical zoom or large sensor (generation dependent)",
        "Wireless + reverse wireless charging on supported models",
        "IP68 dust/water resistance on many flagships — not all ‘Pro’ trims equal; read IP rating",
        "Premium frame materials — titanium / stainless / aluminium grade varies",
        "3–5 years software support story on Apple/Samsung/Pixel lines — verify policy for import units",
    ]
    if tier == "low":
        kf = _pick(r, kf_low_pool, 7)
    elif tier == "mid":
        kf = _pick(r, kf_mid_pool, 7)
    else:
        kf = _pick(r, kf_high_pool, 7)

    if voice == "transsion" and tier != "high":
        kf.append("AI camera tuning + extended RAM marketing — common on Tecno/Infinix Jumia titles")
    if voice == "xiaomi":
        kf.append("MIUI/HyperOS features: second space, dual apps, reading mode — region dependent")
    if voice == "samsung":
        kf.append("One UI: Edge panels, Always On Display, Samsung Knox basics on supported devices")
    if voice == "apple":
        kf.append("iOS: Face ID, iCloud, Find My — ecosystem lock-in as feature")

    # --- What’s in the box (Jumia variability)
    box_standard = ["Handset", "USB cable", "SIM eject tool", "User manual / quick start"]
    if r.random() < 0.35:
        box_standard.append("Protective case (where seller bundles)")
    if r.random() < 0.28:
        box_standard.append("Glass screen protector (where seller bundles)")
    if r.random() < 0.15 and tier == "low":
        box_standard.append("Wired earphones (bundle varies by listing)")
    if voice == "samsung" and r.random() < 0.4:
        box_standard.append("Type-C to Type-C cable — adapter may not be included (check PDP)")
    if r.random() < 0.12:
        box_standard.append("Charging adapter included (confirm — many SKUs are cable-only)")

    return short, desc, kf, box_standard


def tv_marketing_voice(brand: str) -> str:
    if brand in ("Samsung", "LG", "Sony"):
        return "tier1"
    if brand in ("TCL", "Hisense", "Skyworth", "Haier", "Sharp", "Panasonic"):
        return "value_major"
    return "local_value"


def generate_tv_marketing(
    r: random.Random,
    *,
    brand: str,
    tier: str,
    size: int,
    res: str,
    smart: str,
    color: str,
) -> tuple[str, str, list[str]]:
    v = tv_marketing_voice(brand)
    ctx = {"brand": brand, "size": size, "res": res, "smart": smart, "color": color, "tier": tier}

    if tier == "low":
        short_pool = [
            '{brand} {size}" frameless digital LED TV — HD picture, HDMI & USB, AV for decoder/console — '
            "entry lounge or bedroom size popular on Jumia.",
            '{brand} {size}" full-screen LED — wide vision, minimal borders, free-to-air / DVBT2 story where tuner is built-in — '
            "check seller spec for exact tuner type.",
            '{brand} {size}" {res} TV — energy-saving standby messaging, stereo speakers, {color} finish — '
            "value pick vs giant 4K flagships.",
        ]
    elif tier == "mid":
        short_pool = [
            '{brand} {size}" {res} Smart TV — {smart}, HDR-ready processing on supported content, multiple HDMI for console + soundbar.',
            '{brand} {size}" {smart} — stream Netflix/YouTube where apps are licensed; voice remote on some SKUs.',
            '{brand} {size}" QLED/ULED-class marketing on select lines — brighter living-room performance than basic LED.',
        ]
    else:
        short_pool = [
            '{brand} {size}" flagship TV — OLED/Neo QLED / BRAVIA-class processing, 120Hz gaming hooks, eARC for Atmos soundbars.',
            '{brand} {size}" premium panel — film-maker mode, anti-reflection on top trims, metal stand or slim gallery design.',
            '{brand} {size}" cinematic tier — wide colour gamut, precision dimming (technology varies by exact model).',
        ]
    short = r.choice(short_pool).format(**ctx)

    low_desc_bits = [
        "Full screen brings wide vision: the picture spreads across the panel for immersive movies and church services streamed from phone.",
        "Borderless / narrow-bezel language matches Jumia listings: horizon feels wider even at {size} inches.",
        "HDMI connects laptops and decoders; USB plays movies from flash; AV suits older kits—verify port count on your SKU.",
        "Eye-comfort / blue-light style claims appear on budget LED PDPs; viewing angles and glare control vary by panel grade.",
        "Hi-Fi in TV marketing means stereo speakers with clearer dialogue—not home-cinema Atmos unless stated.",
        "Energy-saving standby under ~0.5W is a common bullet; real usage depends on backlight level and content.",
    ]
    mid_desc_bits = [
        "4K UHD step-up: sharper apps, better text for presentations, and headroom for PS5/Xbox Series S|X on supported HDMI 2.1 SKUs.",
        "{smart} brings YouTube, Prime Video, Showmax-style apps where licensed—regional app stores differ from global TVs.",
        "HDR10 / HLG / Dolby Vision support is model-specific; mid TVs beat entry on peak brightness and motion smoothing options.",
        "Voice assistant remotes and Chromecast built-in appear on Android/Google TV SKUs—set up Wi‑Fi once, stream from phone.",
    ]
    high_desc_bits = [
        "Flagship TVs invest in dimming zones or self-emissive pixels (OLED) for contrast; blooming control separates good from great mini-LED.",
        "120Hz native panels and VRR matter for gamers; input lag claims should be verified with reviews, not titles alone.",
        "Build quality: metal frames, cable management, and slim wall-mount profiles—premium tier is also about living-room aesthetics.",
        "HDMI 2.1 ×4, eARC, and codec support (Dolby Atmos passthrough) decide whether one cable to soundbar is enough.",
    ]
    brand_bits = {
        "tier1": [
            "{brand} processing aims for natural skin tones and smooth sports motion—calibration presets differ by region.",
            "Tizen / webOS / Google TV on {brand} flagships: app speed and remote mic quality justify price over no-name panels.",
        ],
        "value_major": [
            "{brand} competes on aggressive pricing with licensed smart platforms—firmware updates fix app crashes; check year/model.",
            "Game Mode Pro / ALLM labels on TCL/Hisense class listings echo Jumia mid-market battlegrounds.",
        ],
        "local_value": [
            "Regional brands stress A+ grade panel, ultra-bright claims, and Android TV badges—compare warranty length vs Samsung/LG.",
            "Bundle deals with wall brackets or HDMI cables appear in marketplace listings; verify what your seller includes.",
        ],
    }

    if tier == "low":
        parts = _pick(r, low_desc_bits, r.randint(3, 5))
    elif tier == "mid":
        parts = _pick(r, mid_desc_bits, r.randint(3, 5))
    else:
        parts = _pick(r, high_desc_bits, r.randint(3, 5))
    parts.extend(_pick(r, brand_bits[v], 2))
    desc = " ".join(p.format(**ctx) if "{" in p else p for p in parts)

    if tier == "low":
        kf = [
            f'{size}" frameless / slim-bezel LED — immersive for size class',
            f"{res} resolution — HD family viewing; sit closer for text clarity",
            "HDMI & USB — consoles, laptops, flash-drive playback",
            "Stereo speakers — clearer dialogue than phone speakers for nightly news",
            "Wall-mount friendly — VESA pattern in manual",
            "Low standby power story — typical of Jumia budget PDP bullets",
        ]
    elif tier == "mid":
        kf = [
            f'{size}" {res} smart TV — {smart}',
            "Multiple HDMI inputs — soundbar + console + decoder",
            "HDR support where listed — streaming quality depends on app and plan",
            "Wi‑Fi + Ethernet on many SKUs — stable 4K streaming",
            "Voice remote on supported models — hands-free search",
        ]
    else:
        kf = [
            f'{size}" flagship-class picture — {res}',
            "High refresh + VRR on gaming-capable SKUs — check HDMI port labels",
            "eARC — single-cable Atmos to compatible soundbars",
            "Premium materials and slim profile — living-room statement piece",
            "Advanced upscaling — SD/HD sources look cleaner on large panels",
        ]
    r.shuffle(kf)
    return short, desc, kf


def sku_safe_brand(brand: str) -> str:
    alnum = "".join(c for c in brand.upper() if c.isalnum())
    return (alnum[:4] or "BRND").ljust(3, "X")


def ugx_price_phone(tier: str, seed: int) -> tuple[int, int | None]:
    r = random.Random(seed)
    if tier == "low":
        base = r.randint(280_000, 650_000)
    elif tier == "mid":
        base = r.randint(720_000, 1_850_000)
    else:
        base = r.randint(2_200_000, 5_200_000)
    compare = int(base * r.uniform(1.05, 1.18)) if r.random() > 0.25 else None
    return base, compare


def ugx_price_tv(tier: str, seed: int) -> tuple[int, int | None]:
    r = random.Random(seed)
    if tier == "low":
        base = r.randint(380_000, 950_000)
    elif tier == "mid":
        base = r.randint(1_050_000, 2_800_000)
    else:
        base = r.randint(3_200_000, 12_500_000)
    compare = int(base * r.uniform(1.04, 1.15)) if r.random() > 0.3 else None
    return base, compare


def build_phone(i: int, tier: str) -> dict[str, Any]:
    r = random.Random(i * 7919 + hash(tier) % 10000)
    brand = r.choice(PHONE_BRANDS[tier])
    if tier == "low":
        series = r.choice(PHONE_SERIES_LOW)
        ram = r.choice([2, 3, 4])
        rom = r.choice([32, 64, 128])
        cam = r.choice([8, 13, 48, 50])
        inch = round(r.uniform(6.1, 6.8), 1)
    elif tier == "mid":
        series = r.choice(PHONE_SERIES_MID)
        ram = r.choice([4, 6, 8])
        rom = r.choice([128, 256])
        cam = r.choice([50, 64, 108])
        inch = round(r.uniform(6.4, 6.9), 1)
    else:
        series = r.choice(PHONE_SERIES_HIGH)
        ram = r.choice([8, 12, 16])
        rom = r.choice([256, 512, 1024])
        cam = r.choice([48, 50, 108, 200])
        inch = round(r.uniform(6.1, 6.9), 1)

    model_num = f"{r.randint(1, 99)}{r.choice(['', 'i', 'e', 's', 'X'])}"
    color = r.choice(COLORS)
    name = f"{brand} {series}{model_num} — {inch}\", {ram}GB+{rom}GB, {cam}MP, {color}"
    sku = f"PHN-{sku_safe_brand(brand)}-{tier[0].upper()}-{i:05d}-{rom}"
    pid = f"prod_phone_{uuid.uuid4().hex[:12]}"
    price, compare = ugx_price_phone(tier, i)

    short, desc, key_features, whats_in_box = generate_phone_marketing(
        r,
        brand=brand,
        tier=tier,
        series=series,
        model_num=model_num,
        inch=inch,
        ram=ram,
        rom=rom,
        cam=cam,
        color=color,
    )

    specs = {
        "display": f'{inch}" ({tier} tier panel)',
        "memory": f"{ram}GB RAM, {rom}GB ROM",
        "camera": f"{cam}MP main + auxiliary sensors",
        "battery": f"{r.choice([4000, 5000, 6000])}mAh typical",
        "os": "Android (version varies)",
        "connectivity": "4G/5G varies by model",
        "sim": "Dual nano-SIM (dual standby)",
        "body": "Glass or composite materials by tier",
    }

    thumb, imgs = image_set_for_product("phone", i)

    return {
        "id": pid,
        "sku": sku,
        "name": name,
        "slug": slugify(name) + f"-{i}",
        "brand": brand,
        "category": "electronics",
        "productType": "phone",
        "tier": tier,
        "currency": "UGX",
        "price": price,
        "compareAtPrice": compare,
        "stockQuantity": r.randint(0, 180),
        "availabilityStatus": r.choice(["in_stock"] * 8 + ["low_stock", "out_of_stock"]),
        "ratingAverage": round(r.uniform(3.4, 4.9), 1),
        "reviewCount": r.randint(0, 2500),
        "shortDescription": short,
        "description": desc,
        "keyFeatures": key_features,
        "specifications": specs,
        "whatsInTheBox": whats_in_box,
        "attributes": {
            "screenInches": inch,
            "ramGb": ram,
            "storageGb": rom,
            "rearCameraMp": cam,
            "color": color,
            "tier": tier,
        },
        "thumbnail": thumb,
        "images": imgs,
        "imageAttribution": "Unsplash (unsplash.com) and Lorem Picsum (picsum.photos); replace with licensed assets for production.",
        "isDuplicateListing": False,
    }


def build_tv(i: int, tier: str) -> dict[str, Any]:
    r = random.Random(i * 11003 + hash(tier) % 10000)
    brand = r.choice(TV_BRANDS[tier])
    if tier == "low":
        series = r.choice(TV_SERIES_LOW)
        size = r.choice([24, 32, 40, 43])
        res = r.choice(["HD Ready", "HD", "1366x768"])
        smart = r.choice(["Smart", "Free-to-Air", "Digital LED"])
    elif tier == "mid":
        series = r.choice(TV_SERIES_MID)
        size = r.choice([43, 50, 55, 58])
        res = "4K UHD"
        smart = r.choice(["Android TV", "Google TV", "webOS", "Tizen"])
    else:
        series = r.choice(TV_SERIES_HIGH)
        size = r.choice([55, 65, 75, 77, 85])
        res = r.choice(["4K UHD", "4K OLED", "4K QLED", "8K"])
        smart = r.choice(["webOS", "Tizen", "Google TV", "Android TV"])

    color = r.choice(["Black", "Graphite", "Silver"])
    name = f'{brand} {size}" {series} {res} — {smart}, {color}'
    sku = f"TEL-{sku_safe_brand(brand)}-{tier[0].upper()}-{i:05d}-{size}"
    pid = f"prod_tv_{uuid.uuid4().hex[:12]}"
    price, compare = ugx_price_tv(tier, i)

    short, desc, key_features = generate_tv_marketing(
        r,
        brand=brand,
        tier=tier,
        size=size,
        res=res,
        smart=smart,
        color=color,
    )

    specs = {
        "screenSizeInches": size,
        "resolution": res,
        "smartPlatform": smart,
        "hdmiPorts": r.randint(2, 4),
        "usbPorts": r.randint(1, 3),
        "refreshRate": "60Hz" if tier == "low" else r.choice(["60Hz", "100Hz", "120Hz"]),
        "hdr": "HDR10" if tier != "low" else "SDR / basic HDR varies",
        "audio": "Stereo; ARC/eARC on mid/high tiers",
        "color": color,
    }

    thumb, imgs = image_set_for_product("tv", i)

    return {
        "id": pid,
        "sku": sku,
        "name": name,
        "slug": slugify(name) + f"-{i}",
        "brand": brand,
        "category": "electronics",
        "productType": "television",
        "tier": tier,
        "currency": "UGX",
        "price": price,
        "compareAtPrice": compare,
        "stockQuantity": r.randint(0, 90),
        "availabilityStatus": r.choice(["in_stock"] * 8 + ["low_stock", "out_of_stock"]),
        "ratingAverage": round(r.uniform(3.3, 4.95), 1),
        "reviewCount": r.randint(0, 1800),
        "shortDescription": short,
        "description": desc,
        "keyFeatures": key_features,
        "specifications": specs,
        "whatsInTheBox": [
            "Television unit",
            "Remote control",
            "User manual",
            "Stand or feet (model dependent)",
        ],
        "attributes": {
            "screenInches": size,
            "resolution": res,
            "smartPlatform": smart,
            "color": color,
            "tier": tier,
        },
        "thumbnail": thumb,
        "images": imgs,
        "imageAttribution": "Unsplash (unsplash.com) and Lorem Picsum (picsum.photos); replace with licensed assets for production.",
        "isDuplicateListing": False,
    }


def add_duplicate_listings(products: list[dict[str, Any]], target_total: int) -> list[dict[str, Any]]:
    """Append duplicate-style rows until len == target_total (same payload, new id/sku/slug)."""
    base = list(products)
    n = len(base)
    need = target_total - n
    if need <= 0:
        return base[:target_total]
    for j in range(need):
        idx = random.randint(0, n - 1)
        p = json.loads(json.dumps(base[idx]))
        orig_id = p["id"]
        p["id"] = orig_id + f"-dup{j}"
        p["sku"] = p["sku"] + f"-D{j}"
        p["slug"] = p["slug"] + f"-listing-{j}"
        p["isDuplicateListing"] = True
        p["duplicateOfId"] = orig_id
        base.append(p)
    return base


def main() -> None:
    unique_per_category = 900
    target_per_category = 1000

    phones = [
        build_phone(i, tier_for_index(i, unique_per_category)) for i in range(unique_per_category)
    ]
    tvs = [build_tv(i, tier_for_index(i, unique_per_category)) for i in range(unique_per_category)]

    phones = add_duplicate_listings(phones, target_per_category)
    tvs = add_duplicate_listings(tvs, target_per_category)

    all_rows = phones + tvs
    root = Path(__file__).resolve().parent.parent
    out_path = root / "data" / "products.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_rows)} lines to {out_path}")
    print(f"Phones: {len(phones)}, TVs: {len(tvs)}")


if __name__ == "__main__":
    main()
