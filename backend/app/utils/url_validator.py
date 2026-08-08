from dataclasses import dataclass
from urllib.parse import urlparse

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}


@dataclass
class ValidationResult:
    valid: bool
    error_code: str = ""
    error_message: str = ""


def validate_url(url: str) -> ValidationResult:
    if len(url) > MAX_URL_LENGTH:
        return ValidationResult(
            valid=False,
            error_code="INVALID_URL",
            error_message=f"URL exceeds the maximum allowed length of {MAX_URL_LENGTH} characters.",
        )

    try:
        parsed = urlparse(url)
    except ValueError:
        return ValidationResult(valid=False, error_code="INVALID_URL", error_message="URL could not be parsed.")

    if parsed.scheme not in ALLOWED_SCHEMES:
        return ValidationResult(
            valid=False,
            error_code="INVALID_URL",
            error_message=f"URL scheme '{parsed.scheme or '(none)'}' is not allowed. Only http and https are supported.",
        )

    if not parsed.netloc:
        return ValidationResult(valid=False, error_code="INVALID_URL", error_message="URL is missing a host.")

    return ValidationResult(valid=True)
