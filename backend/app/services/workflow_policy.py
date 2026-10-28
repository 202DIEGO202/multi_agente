def automatic_approval_allowed(mode, valid, *, complete=True, runtime_verified=True, observations=()):
    """Automatic decisions require a valid, complete result and verified runtime when relevant."""
    return (
        mode == "automatico"
        and bool(valid)
        and bool(complete)
        and bool(runtime_verified)
        and not observations
    )
