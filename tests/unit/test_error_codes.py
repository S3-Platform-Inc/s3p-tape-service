from tape_service.errors import ApiError, ErrorCode


def test_api_error_serialises():
    err = ApiError(ErrorCode.UNAUTHORIZED, "no session")
    assert err.to_dict() == {"error": {"code": "UNAUTHORIZED", "message": "no session"}}
    assert err.status_code == 401


def test_all_codes_have_status():
    for code in ErrorCode:
        assert code.status >= 400


def test_tape_locked_is_409_conflict():
    assert ErrorCode.TAPE_LOCKED.status == 409
    assert ErrorCode.TAPE_LOCKED.code == "TAPE_LOCKED"
