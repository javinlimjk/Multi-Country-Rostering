import os
import requests

class APIService:
    def __init__(self):
        self.api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
        self.api_key = os.getenv("COMPLIANCE_API_KEY", "")
        self.api_headers = {"X-API-Key": self.api_key} if self.api_key else {}

    def check_health(self):
        return requests.get(f"{self.api_url}/", timeout=1)

    def optimize(self, payload):
        return requests.post(f"{self.api_url}/optimize", json=payload, headers=self.api_headers, timeout=30)

    def forecast(self, payload):
        return requests.post(f"{self.api_url}/forecast", json=payload, headers=self.api_headers, timeout=10)

    def validate(self, payload):
        return requests.post(f"{self.api_url}/validate", json=payload, headers=self.api_headers, timeout=15)

    def recommend(self, payload):
        return requests.post(f"{self.api_url}/recommend", json=payload, headers=self.api_headers, timeout=10)

    def agent_chat(self, payload):
        return requests.post(f"{self.api_url}/agent/chat", json=payload, headers=self.api_headers, timeout=15)

    def search_compliance(self, query, country):
        return requests.get(f"{self.api_url}/compliance/search", params={"query": query, "country": country}, headers=self.api_headers)
