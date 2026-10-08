from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_chat():
    response = client.post('/api/chat', json={
        'user_query': 'What is the delay risk for supplier SUP001 and purchase order PO10025?',
        'supplier_id': 'SUP001',
        'purchase_order_id': 'PO10025',
        'product_id': 'PROD100',
    })
    assert response.status_code == 200
    payload = response.json()
    assert 'risk_classification' in payload
    assert 'final_response' in payload
