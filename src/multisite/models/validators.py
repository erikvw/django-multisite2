from django.core.exceptions import ValidationError

__all__ = ["validate_1_or_none", "validate_true_or_none"]


def validate_true_or_none(value: bool | None) -> None:
    """Raises ValidationError if value is not True or None.

    `Alias.is_canonical` is True for the canonical alias and None
    otherwise, so that the `unique_is_canonical_site` constraint
    permits many non-canonical aliases per site. NULLs are distinct.
    """
    if value not in [True, None]:
        raise ValidationError("%r must be True or None" % value)


def validate_1_or_none(value: int | None) -> None:
    """Left in place for migration 0003, which references it.

    `is_canonical` was an IntegerField between migrations 0003 and
    0005. See `validate_true_or_none` for the current field.
    """
