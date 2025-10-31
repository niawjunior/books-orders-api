def clamp_pagination(limit: int, offset: int, max_limit: int = 100):
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset
