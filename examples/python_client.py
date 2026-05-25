"""Minimal Python client for the ollama-rag-api.

Usage:
    python examples/python_client.py "What is this document about?"

Environment:
    API_URL (default: http://localhost:5001)
"""
from __future__ import annotations

import os
import sys
from typing import Any

import requests


class ChatClient:
    def __init__(self, base_url: str | None = None, timeout: int = 300) -> None:
        self.base_url = (base_url or os.getenv("API_URL", "http://localhost:5001")).rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        r = requests.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def ask(self, query: str) -> dict[str, Any]:
        r = requests.post(f"{self.base_url}/ask", json={"query": query}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "What is this document about?"
    client = ChatClient()
    print(f"→ {client.base_url} ({client.health()})")
    result = client.ask(query)
    print(f"\nQ: {result['query']}")
    print(f"A: {result['answer']}")
    print(f"   ({result['time_taken']:.2f}s, {len(result['documents'])} sources)")
