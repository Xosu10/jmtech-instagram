import pytest


@pytest.fixture(autouse=True)
def pruebas_sin_publicacion_real(monkeypatch):
    # Running pytest inside Actions must not activate the production-only
    # video backup, which commits and pushes files to main.
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
