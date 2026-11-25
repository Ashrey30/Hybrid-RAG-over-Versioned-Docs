from guard.access import allowed_groups


def test_public_sees_only_public():
    assert allowed_groups("public") == ["public"]
    assert allowed_groups("anything-else") == ["public"]
    assert "restricted" in allowed_groups("restricted")
