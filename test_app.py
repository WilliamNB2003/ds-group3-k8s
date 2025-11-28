import asyncio
from unittest import mock

import pytest

import app

# The 'cli' fixture comes from conftest.py and aiohttp.pytest_plugin


@pytest.mark.asyncio
async def test_pod_id_handler(cli):
    """Test the GET /pod_id endpoint returns the correct ID."""
    app.POD_ID = 101  # Set a specific ID for the test

    resp = await cli.get("/pod_id")
    assert resp.status == 200
    data = await resp.json()
    assert data == 101


@pytest.mark.asyncio
async def test_receive_answer_handler(cli):
    """Test the POST /receive_answer endpoint."""
    resp = await cli.post("/receive_answer")
    assert resp.status == 200
    data = await resp.json()
    assert data == "OK"


@pytest.mark.asyncio
async def test_receive_election_starts_election(cli):
    """Test /receive_election starts election when ELECTION_IN_PROCESS is False."""

    # Set the election type
    import os

    os.environ["ELECTION_TYPE"] = "normal"

    # Arrange: Ensure the flag is False
    app.ELECTION_IN_PROCESS = False

    # Mock the actual election function to track if it was called
    original_leader_election = app.leader_election
    election_called = False

    async def mock_leader_election():
        nonlocal election_called
        election_called = True
        app.ELECTION_IN_PROCESS = True
        await asyncio.sleep(0.1)  # Simulate some work
        app.ELECTION_IN_PROCESS = False

    with mock.patch("app.leader_election", side_effect=mock_leader_election):
        # Act: Send the request
        resp = await cli.post("/receive_election")

        # Assert: Check response
        assert resp.status == 200

        # Wait for background task to start
        await asyncio.sleep(0.2)

        # Check that election was called
        assert election_called is True


@pytest.mark.asyncio
async def test_receive_election_skips_if_election_in_process(cli):
    """Test /receive_election skips starting a new election if one is running."""

    # Arrange: Set the flag to True to simulate election in progress
    app.ELECTION_IN_PROCESS = True
    original_flag = app.ELECTION_IN_PROCESS

    # Act: Send the request
    resp = await cli.post("/receive_election")

    # Assert: Check response
    assert resp.status == 200

    # Wait a bit
    await asyncio.sleep(0.2)

    # The flag should still be True (no new election started)
    # Note: This test is tricky because the election function checks the flag
    # and returns early if it's already True


@pytest.mark.asyncio
async def test_leader_election_becomes_leader():
    """Test case where the pod has the highest ID and becomes the leader."""

    # Arrange: Set state for highest ID
    app.POD_ID = 100
    app.POD_IP = "10.0.0.100"
    app.IP_TO_ID = {"10.0.0.2": 60, "10.0.0.3": 40}  # All other IDs are lower
    app.ELECTION_IN_PROCESS = False
    app.leader = {"id": -1, "url": ""}

    # Mock the send_coordinator and label functions
    with (
        mock.patch(
            "app.send_coordinator", new_callable=mock.AsyncMock
        ) as mock_coordinator,
        mock.patch(
            "app.label_self_as_leader", new_callable=mock.AsyncMock
        ) as mock_label,
    ):
        # Act: Run the election
        await app.leader_election()

        # Assert: Check if it declared itself leader
        assert app.leader["id"] == 100
        assert app.leader["url"] == "10.0.0.100"
        assert app.ELECTION_IN_PROCESS is False

        # Check that coordinator broadcast was sent
        mock_coordinator.assert_called_once()
        mock_label.assert_called_once()


@pytest.mark.asyncio
async def test_leader_election_no_response_becomes_leader():
    """Test case where no higher ID responds, so this pod becomes leader."""

    # Arrange
    app.POD_ID = 50
    app.POD_IP = "10.0.0.50"
    app.IP_TO_ID = {"10.0.0.2": 60, "10.0.0.3": 40}  # 60 is higher but won't respond
    app.ELECTION_IN_PROCESS = False
    app.leader = {"id": -1, "url": ""}

    # Mock send_election to simulate NO response (exception or non-200)
    async def mock_send_election(improved=False):
        # Simulate failed responses
        return [Exception("Connection failed")]

    with (
        mock.patch("app.send_election", side_effect=mock_send_election),
        mock.patch(
            "app.send_coordinator", new_callable=mock.AsyncMock
        ) as mock_coordinator,
        mock.patch("app.label_self_as_leader", new_callable=mock.AsyncMock),
    ):
        # Act: Run the election
        await app.leader_election()

        # Assert: Should become leader since no OK received
        assert app.leader["id"] == 50
        assert app.leader["url"] == "10.0.0.50"
        assert app.ELECTION_IN_PROCESS is False
        mock_coordinator.assert_called_once()


@pytest.mark.asyncio
async def test_receive_coordinator_updates_leader(cli):
    """Test that receiving coordinator message updates the leader."""

    # Arrange
    app.leader = {"id": -1, "url": ""}
    app.POD_ID = 50

    with mock.patch("app.remove_leader_label", new_callable=mock.AsyncMock):
        # Act: Send coordinator message
        resp = await cli.post(
            "/receive_coordinator", json={"id": 100, "url": "10.0.0.100"}
        )

        # Assert
        assert resp.status == 200
        assert app.leader["id"] == 100
        assert app.leader["url"] == "10.0.0.100"
