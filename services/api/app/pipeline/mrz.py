"""ICAO 9303 MRZ parsing and check-digit validation (TD3 passports).

Implements the field layout and ICAO check-digit algorithm for the TD3
(Machine Readable Passport) zone: two lines of 44 characters. Includes
per-field check-digit validation plus the composite final check digit.
"""
from dataclasses import dataclass, field

WEIGHTS = [7, 3, 1]


def _char_value(ch: str) -> int:
    """ICAO 9303 value for a character: digits 0-9, letters A-Z (10-35), '<' 0."""
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    if ch.isalpha():
        return ord(ch.upper()) - ord("A") + 10
    return 0


def mrz_check_digit(chars: str) -> int:
    """Compute the ICAO 9303 check digit for a character sequence."""
    total = 0
    for i, ch in enumerate(chars):
        total += _char_value(ch) * WEIGHTS[i % 3]
    return total % 10


def validate_mrz_checksum(field: str, check_digit_char: str) -> bool:
    """Validate a field against its check digit character."""
    if len(check_digit_char) != 1 or not check_digit_char.isdigit():
        return False
    return mrz_check_digit(field) == int(check_digit_char)


@dataclass
class MRZResult:
    """Structured, fully-validated MRZ result."""

    mrz_detected: bool = False
    mrz_valid: bool = False
    format: str = ""
    check_digits: dict = field(default_factory=dict)
    parsed_fields: dict = field(default_factory=dict)
    raw_mrz: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_name_block(block: str) -> tuple[str, str]:
    """Split the name block on '<<' into (surname, given_names)."""
    parts = block.split("<<")
    surname = parts[0].replace("<", " ").strip() if parts else ""
    given_names = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    return surname, given_names


def parse_td3(lines: list[str]) -> MRZResult:
    """Parse a TD3 passport MRZ (2 x 44 characters).

    Returns an ``MRZResult`` with per-field check digits, parsed fields,
    raw lines, and warnings. A ``mrz_valid`` of ``True`` requires all
    present check digits to be correct.
    """
    if len(lines) != 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
        return MRZResult(
            mrz_detected=False,
            warnings=["td3_length_mismatch"],
        )

    line1 = lines[0].upper()
    line2 = lines[1].upper()

    # --- Line 1 ---
    document_code = line1[0:2]
    issuing_state = line1[2:5]
    surname, given_names = _parse_name_block(line1[5:44])

    # --- Line 2 ---
    passport_number = line2[0:9]
    def _cd(idx: int) -> str:
        return line2[idx]

    passport_number_check_digit = _cd(9)
    nationality = line2[10:13]
    date_of_birth = line2[13:19]
    date_of_birth_check_digit = _cd(19)
    sex = line2[20]
    expiry_date = line2[21:27]
    expiry_date_check_digit = _cd(27)
    personal_number = line2[28:36]
    personal_number_check_digit = _cd(36)
    optional_data = line2[37:42]
    final_check_digit = _cd(42)

    # --- Per-field validation ---
    checks = {
        "passport_number": validate_mrz_checksum(passport_number, passport_number_check_digit),
        "date_of_birth": validate_mrz_checksum(date_of_birth, date_of_birth_check_digit),
        "expiry_date": validate_mrz_checksum(expiry_date, expiry_date_check_digit),
        # Personal number check is optional (encoded as '<' when absent).
        "personal_number": (
            None
            if personal_number_check_digit == "<"
            else validate_mrz_checksum(personal_number, personal_number_check_digit)
        ),
    }

    # Composite final check digit: covers line2 positions 2:42
    # (from passport_number through optional_data).
    composite = line2[2:42]
    checks["final"] = validate_mrz_checksum(composite, final_check_digit)

    warnings: list[str] = []

    # Validate the date fields conform to YYMMDD.
    import re

    if not re.fullmatch(r"\d{6}", date_of_birth):
        warnings.append("invalid_date_of_birth_format")
    if not re.fullmatch(r"\d{6}", expiry_date):
        warnings.append("invalid_expiry_date_format")

    # document code should begin with 'P' for a passport.
    if not document_code.startswith("P"):
        warnings.append("non_passport_document_code")

    def _all_valid(checks_dict: dict) -> bool:
        return all(v is not False for v in checks_dict.values())

    all_valid = _all_valid(checks)

    parsed = {
        "document_code": document_code,
        "issuing_state": issuing_state,
        "surname": surname,
        "given_names": given_names,
        "passport_number": passport_number,
        "passport_number_check_digit": passport_number_check_digit,
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "date_of_birth_check_digit": date_of_birth_check_digit,
        "sex": sex,
        "expiry_date": expiry_date,
        "expiry_date_check_digit": expiry_date_check_digit,
        "personal_number": personal_number,
        "personal_number_check_digit": personal_number_check_digit,
        "optional_data": optional_data,
        "final_check_digit": final_check_digit,
    }

    return MRZResult(
        mrz_detected=True,
        mrz_valid=all_valid,
        format="TD3",
        check_digits=checks,
        parsed_fields=parsed,
        raw_mrz=[line1, line2],
        warnings=warnings,
    )


def parse_mrz(lines: list[str]) -> MRZResult:
    """Parse MRZ lines, auto-detecting the TD3 format.

    Currently only TD3 (2 x 44) is implemented. Pass through to the TD3
    parser; other formats report as not detected.
    """
    cleaned = [line.upper() for line in lines if line.strip()]
    if not cleaned:
        return MRZResult(mrz_detected=False, warnings=["empty_mrz"])

    if len(cleaned) == 2 and len(cleaned[0]) == 44 and len(cleaned[1]) == 44:
        return parse_td3(cleaned)

    return MRZResult(
        mrz_detected=False,
        warnings=["unrecognized_mrz_format"],
        raw_mrz=cleaned,
    )
