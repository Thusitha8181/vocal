import re

DEFAULT_COUNTRY_CODE = "91"


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_phone(value: str) -> str | None:
    """Normalise spoken or typed numbers ("98765 43210", "+91-98765-43210") to E.164."""
    digits = digits_only(value)
    if not digits:
        return None
    if value.strip().startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+{DEFAULT_COUNTRY_CODE}{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"+{DEFAULT_COUNTRY_CODE}{digits[1:]}"
    return f"+{digits}"


def same_number(a: str, b: str) -> bool:
    """Match on the last 9 digits so country-code and trunk-prefix differences don't matter."""
    da, db = digits_only(a), digits_only(b)
    return len(da) >= 9 and len(db) >= 9 and da[-9:] == db[-9:]
