from fastapi.testclient import TestClient

from nxjob import __version__
from nxjob.main import create_app


def test_runtime_version_matches_release_line() -> None:
    assert __version__ == "0.6.2"


def test_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nxjob-local-service",
        "version": __version__,
    }

