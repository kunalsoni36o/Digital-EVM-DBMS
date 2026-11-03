"""
app/utils/validators.py – input validation helpers.
"""
import re
from datetime import date


# EPIC number: exactly 3 uppercase letters followed by 7 digits
EPIC_RE = re.compile(r'^[A-Z]{3}\d{7}$')


def validate_epic(epic: str) -> str | None:
    """
    Return a cleaned (uppercased, stripped) EPIC number, or raise ValueError.
    """
    epic = epic.strip().upper()
    if not EPIC_RE.match(epic):
        raise ValueError("EPIC number must be 3 letters followed by 7 digits (e.g. ABC1234567).")
    return epic


def validate_age(dob: date, min_age: int = 18) -> None:
    """Raise ValueError if *dob* is less than *min_age* years ago."""
    today = date.today()
    birthday_this_year = dob.replace(year=today.year)
    age = today.year - dob.year - (1 if birthday_this_year > today else 0)
    if age < min_age:
        raise ValueError(f"You must be at least {min_age} years old to register.")


def validate_password(password: str) -> None:
    """
    Raise ValueError if *password* does not meet the policy:
    - Minimum 8 characters
    - At least one letter
    - At least one digit
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r'[A-Za-z]', password):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit.")


def validate_receipt_code(code: str) -> str:
    """Normalize a receipt code to uppercase, strip spaces, return 16-char string."""
    code = code.strip().upper().replace(" ", "")
    if len(code) != 16:
        raise ValueError("Receipt code must be exactly 16 characters.")
    return code

