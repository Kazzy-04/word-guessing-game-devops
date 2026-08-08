import os 

os.environ["SECRET_KEY"]="test-secret"

from app import app

def test_health():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "UP"
    