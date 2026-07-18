#!/usr/bin/env python3
"""
Health check script — verifies all components are ready.

Run this after deployment to confirm everything works:
    python scripts/health_check.py
"""

import sys

import httpx


def main():
    base_url = "http://localhost:8000"

    print("Machine Manual RAG — Health Check")
    print("=" * 50)

    try:
        resp = httpx.get(f"{base_url}/health", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        print("✗ Cannot connect to RAG API at", base_url)
        print("  Is the server running?")
        print("  Start with: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        sys.exit(1)

    checks = [
        ("Overall Status", data.get("status", "unknown")),
        ("Ollama Connected", data.get("ollama_connected", False)),
        ("Vision Model Available", data.get("ollama_model_available", False)),
        ("Embedding Model Loaded", data.get("embedding_model_loaded", False)),
        ("Reranker Loaded", data.get("reranker_loaded", False)),
        ("Vector Store Ready", data.get("vector_store_ready", False)),
    ]

    all_ok = True
    for name, value in checks:
        if isinstance(value, bool):
            icon = "✓" if value else "✗"
            if not value:
                all_ok = False
        else:
            icon = "✓" if value == "healthy" else "⚠"
            if value != "healthy":
                all_ok = False
        print(f"  {icon} {name}: {value}")

    print()
    print(f"  Manuals indexed: {data.get('manuals_indexed', 0)}")
    print(f"  Total chunks:    {data.get('total_chunks', 0)}")
    print()

    if all_ok:
        print("✓ All systems operational!")
    else:
        print("⚠ Some components are not ready. Check the details above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
