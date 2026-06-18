from src.api.validation import validate_request


def test_validate_request_requires_name() -> None:
    assert not validate_request({})

