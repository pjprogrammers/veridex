#!/usr/bin/env python3
"""VERIDEX synthetic document generator.

Renders realistic-looking, entirely synthetic identity/travel documents
(passport page + national ID) into data/synthetic/. The passport includes a
machine-readable zone (MRZ) that follows the ICAO 9303 TD3 layout with valid
check digits, so the backend MRZ parser accepts it.

Usage:
    python scripts/synthetic_documents.py            # write all documents
    python scripts/synthetic_documents.py --list     # list known doc numbers

Only synthetic identities are used. No real PII.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "synthetic"

# Matches KNOWN_DOCS in services/api/app/core/seed.py
ISSUING_COUNTRY = "SYN"  # "Synthetic"

DOCS = [
    {
        "kind": "passport",
        "doc_number": "P12345678",
        "surname": "SMITH",
        "given": "JORDAN",
        "dob": "910415",  # 1991-04-15
        "expiry": "360415",  # 2036-04-15
        "sex": "M",
        "nationality": "GBR",
        "personal": "ZE184226",
    },
    {
        "kind": "national_id",
        "doc_number": "N87654321",
        "surname": "JOHNSON",
        "given": "ALEX",
        "dob": "870223",
        "expiry": "310223",  # 2031-02-23
        "sex": "F",
        "nationality": "IND",
        "personal": "ID2244668",
    },
]

_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<"


def icao_cd(field: str) -> str:
    """ICAO 9303 check digit with weights 7,3,1 repeating."""
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(field.upper()):
        value = _CHARSET.index(ch) if ch in _CHARSET else 0
        total += value * weights[i % 3]
    return str(total % 10)


def build_mrz_lines(doc: dict) -> tuple[str, str]:
    """Build TD3 (passport) MRZ lines with computed check digits."""
    nums = doc["doc_number"]
    dob = doc["dob"]
    exp = doc["expiry"]
    personal = doc["personal"]

    line1 = (
        "P<"
        + doc["nationality"][:3]
        + doc["surname"]
        + "<<"
        + doc["given"]
    ).ljust(44, "<")

    pass_num_cd = icao_cd(nums)
    dob_cd = icao_cd(dob)
    exp_cd = icao_cd(exp)
    personal_cd = icao_cd(personal)
    subject = f"{nums}{pass_num_cd}{doc['nationality'][:3]}"
    date_block = f"{dob}{dob_cd}{doc['sex']}{exp}{exp_cd}"
    tail = f"{subject}{date_block}{personal}{personal_cd}<<"
    line2 = tail.ljust(43, "<")
    line2 = line2 + icao_cd(line2)  # final composite check digit -> 44 chars
    return line1, line2


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=1 if bold and "noto" in path else 0)
            except Exception:
                pass
    return ImageFont.load_default()


def _text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def make_passport(doc: dict) -> Image.Image:
    W, H = 1000, 660
    img = Image.new("RGB", (W, H), "#f5f0e6")
    d = ImageDraw.Draw(img)

    # Decorative background band
    d.rectangle([0, 0, W, 90], fill="#1b3a5c")
    d.rectangle([0, 88, W, 94], fill="#b9792f")
    d.rectangle([0, 0, W, 90], outline="#12304e", width=2)

    band_font = _font(30, True)
    title = "REPUBLIC OF SYNTHETICA"
    d.text(((W - _text_w(d, title, band_font)) / 2, 18), title, fill="white", font=band_font)
    sub = "PASSPORT"
    d.text(((W - _text_w(d, sub, band_font)) / 2, 52), sub, fill="#f0c674", font=band_font)

    # Bold mono header
    h = _font(20, True)
    fields = [
        ("NATIONALITY", doc["nationality"]),
        ("DOCUMENT NO", doc["doc_number"]),
        ("SEX", doc["sex"]),
    ]
    x = 80
    y0 = 150
    for label, value in fields:
        d.text((x, y0), label, fill="#5b5b5b", font=h)
        d.text((x, y0 + 34), value, fill="#111111", font=_font(26, True))
        x += 300

    # Personal data block on the left
    y = 265
    for label, value in [
        ("SURNAME", doc["surname"]),
        ("GIVEN NAME", doc["given"]),
        ("DATE OF BIRTH", f"{doc['dob'][:2]}-{doc['dob'][2:4]}-{doc['dob'][4:]}"),
        ("DATE OF EXPIRY", f"{doc['expiry'][:2]}-{doc['expiry'][2:4]}-{doc['expiry'][4:]}"),
        ("PERSONAL NO", doc["personal"]),
    ]:
        d.text((80, y), label, fill="#5b5b5b", font=h)
        d.text((80, y + 30), value, fill="#111111", font=_font(24, True))
        y += 76

    # Portrait placeholder: stylized silhouette
    px, py, pw, ph = 640, 265, 250, 330
    d.rectangle([px, py, px + pw, py + ph], outline="#b9792f", width=3)
    d.rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], fill="#eee7d8", outline="#c9bfa8")
    d.ellipse([px + 55, py + 22, px + 195, py + 150], fill="#d8a47f")
    d.polygon(
        [(px + 20, py + ph - 26), (px, py + ph - 12), (px + pw, py + ph - 12), (px + pw - 20, py + ph - 26)],
        fill="#5a6472",
    )
    d.rectangle([px + 42, py + 165, px + 208, py + 292], fill="#3d5466")

    # MRZ zone
    mrz_y = 500
    d.rectangle([0, mrz_y, W, H], fill="#10212f")
    font = _font(30)
    line1, line2 = build_mrz_lines(doc)

    # Draw as evenly spaced cells to mimic OCR-B machine readability
    for i, ch in enumerate(line1):
        d.text((16 + i * 27, mrz_y + 22), ch, fill="#e8f1e8" if ch != "<" else "#7f9aa8", font=font)
    for i, ch in enumerate(line2):
        d.text((16 + i * 27, mrz_y + 74), ch, fill="#e8f1e8" if ch != "<" else "#7f9aa8", font=font)

    return img


def make_national_id(doc: dict) -> Image.Image:
    W, H = 900, 560
    img = Image.new("RGB", (W, H), "#eef2f5")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 64], fill="#7a1f3d")
    d.text(((W - _text_w(d, "NATIONAL IDENTITY CARD", _font(26, True))) / 2, 16),
           "NATIONAL IDENTITY CARD", fill="white", font=_font(26, True))

    y = 110
    for label, value in [
        ("SURNAME", doc["surname"]),
        ("GIVEN NAME", doc["given"]),
        ("DATE OF BIRTH", f"{doc['dob'][:2]}-{doc['dob'][2:4]}-{doc['dob'][4:]}"),
        ("SEX", doc["sex"]),
        ("ID NUMBER", doc["doc_number"]),
        ("VALID UNTIL", f"{doc['expiry'][:2]}-{doc['expiry'][2:4]}-{doc['expiry'][4:]}"),
    ]:
        d.text((80, y), label, fill="#5b5b5b", font=_font(16, True))
        d.text((80, y + 26), value, fill="#111111", font=_font(22, True))
        y += 64

    px, py, pw, ph = 620, 100, 220, 300
    d.rectangle([px, py, px + pw, py + ph], outline="#7a1f3d", width=3)
    d.ellipse([px + 40, py + 20, px + pw - 40, py + 130], fill="#d8a47f")
    d.rectangle([px + 30, py + 150, px + pw - 30, py + 260], fill="#46607a")

    d.text((80, y + 4), f"MACHINE VERIFICATION REF: {doc['personal']}", fill="#2f4f6f", font=_font(16, True))
    return img


# ---------------------------------------------------------------------------
# SIH demo scenario assets
#
# The demo-scenario selector on the /verify page drives the *real* API
# pipeline; each scenario only supplies a synthetic input document (and, for
# the impersonation case, a distinctly different synthetic "live face"). All
# results on the results page come from actual API responses.
# ---------------------------------------------------------------------------

DEMO_SCENARIOS = {
    "genuine": {
        "doc": {"kind": "passport", "doc_number": "P12345678", "surname": "SMITH",
                 "given": "JORDAN", "dob": "910415", "expiry": "360415",
                 "sex": "M", "nationality": "GBR", "personal": "ZE184226"},
        "file": "genuine_passport.png",
    },
    "tampered": {
        "doc": {"kind": "passport", "doc_number": "P12345678", "surname": "SMITH",
                 "given": "JORDAN", "dob": "910415", "expiry": "360415",
                 "sex": "M", "nationality": "GBR", "personal": "ZE184226"},
        "file": "tampered_passport.png",
    },
    "expired": {
        "doc": {"kind": "passport", "doc_number": "Q88776655", "surname": "OBI",
                 "given": "MARIA", "dob": "820617", "expiry": "080915",
                 "sex": "F", "nationality": "NGA", "personal": "XA0011223"},
        "file": "expired_passport.png",
    },
    "blacklisted": {
        "doc": {"kind": "passport", "doc_number": "B55544433", "surname": "CHEN",
                 "given": "MORGAN", "dob": "900310", "expiry": "260310",
                 "sex": "F", "nationality": "USA", "personal": "BL00112233"},
        "file": "blacklisted_passport.png",
    },
}


def _splice_patch(img: Image.Image) -> Image.Image:
    """Simulate a crude retouch: paste a mismatched texture patch over the
    date field and re-encode at a different JPEG quality. The forensics engine
    measures ELA / noise / splice anomalies on real pixels."""
    out = img.copy()
    d = ImageDraw.Draw(out)
    px, py, pw, ph = 360, 380, 200, 70
    patch = Image.new("RGB", (pw, ph), "#cfc4b0")
    noise = Image.effect_noise((pw, ph), 24).convert("RGB")
    patch = Image.blend(patch, noise, 0.35)
    out.paste(patch, (px, py))
    d.rectangle([px, py, px + pw, py + ph], outline="#b9792f", width=2)
    # Re-encode through JPEG to destroy original compression fingerprint
    tmp = out.convert("RGB")
    tmp.save("/tmp/_tamper_tmp.jpg", "JPEG", quality=62)
    return Image.open("/tmp/_tamper_tmp.jpg")


def make_live_face(doc: dict, variant: str) -> Image.Image:
    """Synthetic 'live selfie' portraits (stylized, like the document photos).

    ``variant="selfie"`` reuses the document portrait styling so the baseline
    face engine sees a near-identical face region (high similarity).
    ``variant="other"`` renders a clearly different person (low similarity),
    used by the Impersonation scenario.
    """
    W, H = 480, 640
    img = Image.new("RGB", (W, H), "#c9cdd4")
    d = ImageDraw.Draw(img)

    # Room / background band to look like a selfie
    d.rectangle([0, H - 120, W, H], fill="#8b929c")

    skin = "#d8a47f" if variant == "selfie" else "#7a4a2f"
    shirt = "#3d5466" if variant == "selfie" else "#2c3038"

    # Head
    d.ellipse([W // 2 - 130, 60, W // 2 + 130, 430], fill=skin)
    # Shirt / shoulders
    d.polygon([(W // 2 - 220, H - 40), (W // 2 + 220, H - 40), (W // 2 + 170, 330),
               (W // 2 - 170, 330)], fill=shirt)
    # Hair cap
    hair = "#39291e" if variant == "selfie" else "#16181c"
    d.ellipse([W // 2 - 132, 52, W // 2 + 132, 210], fill=hair)
    d.rectangle([W // 2 - 132, 185, W // 2 + 132, 205], fill=hair)
    # Eyes / brows
    ecol = "#3a2c1f"
    d.ellipse([W // 2 - 70, 225, W // 2 - 28, 265], fill="white")
    d.ellipse([W // 2 + 28, 225, W // 2 + 70, 265], fill="white")
    d.ellipse([W // 2 - 62, 238, W // 2 - 38, 254], fill=ecol)
    d.ellipse([W // 2 + 38, 238, W // 2 + 62, 254], fill=ecol)
    d.rectangle([W // 2 - 78, 208, W // 2 - 22, 222], fill=hair)
    d.rectangle([W // 2 + 22, 208, W // 2 + 78, 222], fill=hair)
    # Nose
    d.polygon([(W // 2, 265), (W // 2 - 18, 330), (W // 2 + 18, 330)], fill="#c18a63" if variant == "selfie" else "#5e3a26")
    # Mouth
    d.arc([W // 2 - 42, 330, W // 2 + 42, 395], 0, 180, fill="#b06a4e" if variant == "selfie" else "#4a2b1c", width=7)

    return img


def make_demo_assets(out_dir: Path) -> None:
    """Render all SIH demo scenario input assets."""
    out_dir.mkdir(parents=True, exist_ok=True)

    for key, spec in DEMO_SCENARIOS.items():
        doc = spec["doc"]
        name = spec["file"]
        img = make_passport(doc) if doc["kind"] == "passport" else make_national_id(doc)
        if key == "tampered":
            img = _splice_patch(img)
        out = out_dir / name
        img.save(out)
        print(f"wrote {out}")

    # Impersonation live face (different person) — produces a real face
    # no_match verdict against the passport portrait.
    other = make_live_face(DEMO_SCENARIOS["genuine"]["doc"], "other")
    out = out_dir / "live_other.png"
    other.save(out)
    print(f"wrote {out}")

    # Genuine live selfie (same person styling) — optional high-similarity
    # companion for the genuine / multiple-identity scenarios.
    selfie = make_live_face(DEMO_SCENARIOS["genuine"]["doc"], "selfie")
    out = out_dir / "live_selfie.png"
    selfie.save(out)
    print(f"wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print known document numbers")
    parser.add_argument("--demo", action="store_true",
                        help="write SIH demo scenario assets into data/synthetic/demo")
    args = parser.parse_args()

    if args.list:
        for d in DOCS:
            print(f"{d['kind']:14} {d['doc_number']}  {d['surname']}, {d['given']}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for doc in DOCS:
        img = make_passport(doc) if doc["kind"] == "passport" else make_national_id(doc)
        out = OUT_DIR / f"{doc['kind']}_{doc['doc_number']}.png"
        img.save(out)
        m1, m2 = build_mrz_lines(doc)
        print(f"wrote {out}")
        print(f"  MRZ1: {m1}")
        print(f"  MRZ2: {m2}")

    if args.demo:
        make_demo_assets(OUT_DIR / "demo")


if __name__ == "__main__":
    sys.exit(main())
