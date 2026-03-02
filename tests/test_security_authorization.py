
import unittest
import os
from fastapi.testclient import TestClient

# Set dummy API key for testing
os.environ["COMPLIANCE_API_KEY"] = "testkey"

# Import app (this will use the env var set above)
from app.main import app

class TestSecurityFix(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.valid_headers = {"X-API-Key": "testkey"}

    def test_forecast_unauthorized(self):
        # Should now be 403 Forbidden
        response = self.client.post("/forecast", json={})
        self.assertEqual(response.status_code, 403)

    def test_optimize_unauthorized(self):
        response = self.client.post("/optimize", json={})
        self.assertEqual(response.status_code, 403)

    def test_recommend_unauthorized(self):
        response = self.client.post("/recommend", json={})
        self.assertEqual(response.status_code, 403)

    def test_metrics_unauthorized(self):
        response = self.client.post("/metrics", json={})
        self.assertEqual(response.status_code, 403)

    def test_agent_chat_unauthorized(self):
        response = self.client.post("/agent/chat", json={})
        self.assertEqual(response.status_code, 403)

    def test_demand_unauthorized(self):
        response = self.client.get("/demand/SIN")
        self.assertEqual(response.status_code, 403)

    def test_validate_unauthorized(self):
        response = self.client.post("/validate", json={})
        self.assertEqual(response.status_code, 403)

    def test_forecast_authorized(self):
        # Should NOT be 403 (could be 422 for bad payload, but authorization passed)
        response = self.client.post("/forecast", json={}, headers=self.valid_headers)
        self.assertNotEqual(response.status_code, 403)

    def test_optimize_authorized(self):
        response = self.client.post("/optimize", json={}, headers=self.valid_headers)
        self.assertNotEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
