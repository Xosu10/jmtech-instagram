import pytest


@pytest.fixture(autouse=True)
def pruebas_sin_publicacion_real(monkeypatch):
    # Running pytest inside Actions must not activate the production-only
    # video backup, which commits and pushes files to main.
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)


@pytest.fixture(autouse=True)
def imagenes_reproducibles_en_la_nube(monkeypatch, tmp_path):
    # Tests must not silently use illustrations that only exist on the
    # developer's Windows desktop and are absent from GitHub runners.
    from jmtech import curiosidad
    monkeypatch.setattr(curiosidad, "CARPETA_IMAGENES", tmp_path / "entregas")
