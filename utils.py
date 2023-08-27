from datetime import datetime, timezone


def utc_now():
    """We use this function to get the current time in UTC. It's a bit weird to have this in a separate file, but it's
    for the future implementation so we can change all the timestamps to a different format in one place."""

    return datetime.now(timezone.utc)
