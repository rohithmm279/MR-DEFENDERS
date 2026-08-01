from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_consumer_response_has_retrieved_citation():
    response = client.post("/api/v1/chat", json={"query": "How do I file a consumer complaint for a defective product?"})
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "answered"
    assert body["domain"] == "consumer"
    assert body["citations"][0]["act_name"] == "Consumer Protection Act, 2019"


def test_criminal_response_is_cited():
    response = client.post("/api/v1/chat", json={"query": "How can I give FIR information to police?"})
    body = response.json()
    assert body["status"] == "answered"
    assert body["citations"][0]["section_number"] == "Section 173"
    assert body["confidence"] < 1.0
    checklist = next(block for block in body["blocks"] if block["type"] == "procedure")
    assert checklist["title"] == "Step-by-Step Procedural Guidance"
    assert any("Required documents" in line for line in checklist["content"])
    assert all(citation["section_number"] == "Section 173" for citation in body["citations"])


def test_health_response_contains_readiness_fields():
    response = client.get("/api/v1/health")
    body = response.json()
    assert response.status_code == 200
    assert "verified_records" in body
    assert "chroma_collection_exists" in body


def test_family_response_is_cited():
    response = client.post("/api/v1/chat", json={"query": "What does law say about dowry?"})
    assert response.json()["status"] == "answered"
    assert response.json()["domain"] == "family"


def test_crisis_bypasses_generation():
    response = client.post("/api/v1/chat", json={"query": "There is domestic violence now and I am unsafe at home"})
    body = response.json()
    assert body["status"] == "escalated"
    assert body["citations"] == []


def test_out_of_scope_query_is_refused():
    response = client.post("/api/v1/chat", json={"query": "How do I file my income tax return?"})
    assert response.json()["status"] == "out_of_scope"
