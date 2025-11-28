import os
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web

# Import your application file
mock_k8s_config = patch("kubernetes.config.load_incluster_config")
mock_k8s_client = patch("kubernetes.client.CoreV1Api")

os.environ["POD_NAME"] = "test-pod"
os.environ["POD_IP"] = "10.0.0.1"
os.environ["WEB_PORT"] = "8080"

patch("kubernetes.config.load_incluster_config", MagicMock()).start()
patch("kubernetes.client.CoreV1Api", MagicMock()).start()

import app


@pytest.fixture
def cli(loop, aiohttp_client):
    """Fixture to create a test client for your aiohttp application."""
    # Note: We are using a simplified app creation here for testing,
    # often you need to pass mocked environment variables or state.
    app.v1 = MagicMock()
    # We'll use the application creation logic from your app.py
    test_app = web.Application()
    test_app.router.add_get("/pod_id", app.pod_id)
    test_app.router.add_post("/receive_answer", app.receive_answer)
    test_app.router.add_post("/receive_election", app.receive_election)
    test_app.router.add_post("/receive_coordinator", app.receive_coordinator)
    # Background tasks (run_bully) are often excluded from unit tests
    # and tested separately or via integration tests.

    # Mock global state initialization for consistency in tests
    app.POD_IP = "10.0.0.1"
    app.WEB_PORT = 8080
    app.POD_ID = 50
    app.leader = {"id": -1, "url": ""}
    app.ELECTION_IN_PROCESS = False
    app.IP_TO_ID = {"10.0.0.2": 60, "10.0.0.3": 40}

    return loop.run_until_complete(aiohttp_client(test_app))
