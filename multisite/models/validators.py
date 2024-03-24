from django.core.exceptions import ValidationError

__all__ = ["validate_1_or_none"]


def validate_1_or_none(value: bool) -> None:
    """Raises ValidationError if value is not int(1) or None."""
    if value not in [1, None]:
        raise ValidationError("%r must be 1 or None" % value)


def validate_true_or_none(value: bool) -> None:
    # leave for old migrations
    pass
