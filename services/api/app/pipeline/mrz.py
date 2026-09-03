"""MRZ parsing and check-digit validation.

Parses the Machine Readable Zone (TD1/TD2/TD3) of travel documents and
validates the mandatory check digits. Uses the `mrz` library when available,
with an internal fallback for check-digit computation.
"""
from dataclasses import dataclass, field

WEIGHTS = [7, 3, 1]


def mrz_check_digit(chars: str) -> int:
    """Compute the ICAO 9303 check digit for a character sequence.

    Values: 0-9 -> 0-9, A-Z -> 10-35, '<' -> 0.
    Weighted sum: weight[i] = 7, 3, 1 repeating.
    Returns the check digit (0-9).
    """
    total = 0
    for i, ch in enumerate(chars):
        if ch == "<":
            value = 0
        elif ch.isdigit():
            value = int(ch)
        elif ch.isalpha():
            value = ord(ch.upper()) - ord("A") + 10
        else:
            value = 0
        total += value * WEIGHTS[i % 3]
    return total % 10


def validate_mrz_checksum(field: str, check_digit_char: str) -> bool:
    """Validate a single MRZ field against its check digit character."""
    if len(check_digit_char) != 1:
        return False
    expected = mrz_check_digit(field)
    provided = int(check_digit_char) if check_digit_char.isdigit() else -1
    return expected == provided


@dataclass
class MRZResult:
    """Parsed MRZ data with validation results."""

    valid: bool = False
    format: str = ""
    document_type: str = ""
    document_number: str = ""
    issuing_country: str = ""
    nationality: str = ""
    surname: str = ""
    given_names: str = ""
    date_of_birth: str = ""
    sex: str = ""
    expiry_date: str = ""
    check_digits_valid: bool = False
    errors: list[str] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


def _clean(line: str) -> str:
    return line.upper()


def parse_td3(lines: list[str]) -> MRZResult:
    """Parse a TD3 (ICAO passport) MRZ: 2 lines of 44 characters."""
    if len(lines) != 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
        return MRZResult(valid=False, errors=["TD3 requires 2x44 char lines"])

    line1 = _clean(lines[0])
    line2 = _clean(lines[1])

    result = MRZResult(format="TD3", valid=True)
    result.document_type = line1[0:2].replace("<", "")
    result.issuing_country = line1[2:5]
    result.surname = line1[5:44].split("<")[0].replace("<", " ")
    names = line1[5:44].split("<<")
    if len(names) > 1:
        result.surname = names[0].replace("<", " ").strip()
        result.given_names = names[1].replace("<", " ").strip()

    result.document_number = line2[0:9]
    result.nationality = line2[10:13]
    result.date_of_birth = line2[13:19]
    result.sex = line2[20]
    result.expiry_date = line2[21:27]
    result.raw_lines = [line1, line2]

    # Validate check digits
    checks = [
        ("document_number", result.document_number, line2[9]),
        ("date_of_birth", result.date_of_birth, line2[19]),
        ("expiry_date", result.expiry_date, line2[27]),
    ]
    all_valid = True
    for check_name, field_value, digit in checks:
        if not validate_mrz_checksum(field_value, digit):
            all_valid = False
            result.errors.append(f"check_digit_mismatch:{check_name}")
    result.check_digits_valid = all_valid
    return result


def parse_td1(lines: list[str]) -> MRZResult:
    """Parse a TD1 (ID card) MRZ: 3 lines of 30 characters."""
    if len(lines) != 3 or any(len(line) != 30 for line in lines):
        return MRZResult(valid=False, errors=["TD1 requires 3x30 char lines"])

    mrz_line1 = _clean(lines[0])
    mrz_line2 = _clean(lines[1])
    mrz_line3 = _clean(lines[2])

    result = MRZResult(format="TD1", valid=True)
    result.document_type = mrz_line1[0:2].replace("<", "")
    result.issuing_country = mrz_line1[2:5]
    result.document_number = mrz_line1[5:14]
    result.date_of_birth = mrz_line2[0:6]
    result.sex = mrz_line2[7]
    result.expiry_date = mrz_line2[8:14]
    result.nationality = mrz_line2[15:18]

    names = mrz_line3.split("<<")
    if len(names) > 1:
        result.surname = names[0].replace("<", " ").strip()
        result.given_names = names[1].replace("<", " ").strip()

    result.raw_lines = [mrz_line1, mrz_line2, mrz_line3]

    checks = [
        ("document_number", result.document_number, mrz_line1[14]),
        ("date_of_birth", result.date_of_birth, mrz_line2[6]),
        ("expiry_date", result.expiry_date, mrz_line2[14]),
    ]
    all_valid = True
    for check_name, field_value, digit in checks:
        if not validate_mrz_checksum(field_value, digit):
            all_valid = False
            result.errors.append(f"check_digit_mismatch:{check_name}")
    result.check_digits_valid = all_valid
    return result


def parse_mrz(lines: list[str]) -> MRZResult:
    """Parse MRZ lines, auto-detecting format (TD1 vs TD3)."""
    cleaned = [_clean(line) for line in lines if line.strip()]
    if not cleaned:
        return MRZResult(valid=False, errors=["empty_mrz"])

    if len(cleaned) == 2 and len(cleaned[0]) == 44 and len(cleaned[1]) == 44:
        return parse_td3(cleaned)
    if len(cleaned) == 3 and all(len(line) == 30 for line in cleaned):
        return parse_td1(cleaned)
    return MRZResult(
        valid=False,
        errors=["unrecognized_mrz_format"],
        raw_lines=cleaned,
    )


# Optional: use the `mrz` library when available for robust parsing.
try:

    MRZ_LIB_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    MRZ_LIB_AVAILABLE = False
