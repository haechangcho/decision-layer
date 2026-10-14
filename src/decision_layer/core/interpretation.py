"""Interpretation compatibility without rewriting historical result labels."""


def supports_interpretation(required: str, actual: str | None) -> bool:
    if required == "descriptive":
        # Preserve the original goal contract; new goals should be explicit.
        return True
    if required == "association":
        return actual in ("association", "descriptive", "associational")
    # Legacy associational goals remain strict rather than weakening old contracts.
    return actual == required
