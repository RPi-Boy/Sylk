"""
Sylk FaaS API — End-to-End Test Script
=======================================
Tests the full lifecycle:
  1. Deploy a Python function
  2. Deploy a Node.js function
  3. Invoke each function with parameters
  4. List all deployed functions

Usage:
  python test_api.py [CONTROL_PLANE_URL]

  Default: http://localhost:8000
"""

import requests
import sys
import json
import time

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def separator(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_deploy_python():
    separator("1. Deploy Python Function")
    payload = {
        "slug": "greet-py",
        "language": "python",
        "code": 'name = params.get("name", "World")\nprint(f"Hello, {name}! from Python on Sylk")',
    }
    resp = requests.post(f"{BASE_URL}/functions", json=payload)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    if resp.status_code == 409:
        print("Function already exists — that's OK, continuing.")
    return data


def test_deploy_node():
    separator("2. Deploy Node.js Function")
    payload = {
        "slug": "greet-js",
        "language": "node",
        "code": 'const name = params.name || "World";\nconsole.log(`Hello, ${name}! from Node.js on Sylk`);',
    }
    resp = requests.post(f"{BASE_URL}/functions", json=payload)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    if resp.status_code == 409:
        print("Function already exists — that's OK, continuing.")
    return data


def test_invoke_python():
    separator("3. Invoke Python Function: /fn/greet-py")
    payload = {"params": {"name": "Sylk Hackathon"}}
    print(f"Sending params: {json.dumps(payload)}")
    print("Waiting for synchronous response (up to 30s)...")
    start = time.time()
    resp = requests.post(f"{BASE_URL}/fn/greet-py", json=payload, timeout=35)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} (took {elapsed:.2f}s)")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data


def test_invoke_node():
    separator("4. Invoke Node.js Function: /fn/greet-js")
    payload = {"params": {"name": "Edge Mesh"}}
    print(f"Sending params: {json.dumps(payload)}")
    print("Waiting for synchronous response (up to 30s)...")
    start = time.time()
    resp = requests.post(f"{BASE_URL}/fn/greet-js", json=payload, timeout=35)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} (took {elapsed:.2f}s)")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data


def test_list_functions():
    separator("5. List All Deployed Functions")
    resp = requests.get(f"{BASE_URL}/functions")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Functions ({len(data)}):")
    for fn in data:
        print(f"  - [{fn['language']}] {fn['slug']}  →  {fn['endpoint']}")
    return data


def test_invoke_default_params():
    separator("6. Invoke Python Function with NO params (default)")
    payload = {"params": {}}
    start = time.time()
    resp = requests.post(f"{BASE_URL}/fn/greet-py", json=payload, timeout=35)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} (took {elapsed:.2f}s)")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data


if __name__ == "__main__":
    print("Sylk FaaS API Test Suite")
    print(f"Target: {BASE_URL}")

    # Deploy
    test_deploy_python()
    test_deploy_node()

    # List
    test_list_functions()

    # Invoke (these block until worker responds)
    test_invoke_python()
    test_invoke_node()
    test_invoke_default_params()

    separator("ALL TESTS COMPLETE")
    print("If you saw outputs above, the FaaS pipeline is working end-to-end!")
