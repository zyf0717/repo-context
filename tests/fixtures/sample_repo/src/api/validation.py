def validate_request(payload: dict[str, object]) -> bool:
    if "name" not in payload:
        return False
    return isinstance(payload["name"], str)

