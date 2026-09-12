from app.core.config import Settings


def test_secret_key_is_required() -> None:
    assert Settings.model_fields["SECRET_KEY"].is_required()
