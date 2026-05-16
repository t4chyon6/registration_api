import registration


def test_registration_package_is_importable() -> None:
    assert registration.__name__ == "registration"
