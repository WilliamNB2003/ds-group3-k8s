import pytest
from unittest import mock
import app 

# The 'cli' fixture comes from conftest.py and aiohttp.pytest_plugin

@pytest.mark.asyncio
async def test_pod_id_handler(cli):
    """Test the GET /pod_id endpoint returns the correct ID."""
    app.POD_ID = 101 # Set a specific ID for the test
    
    resp = await cli.get('/pod_id')
    assert resp.status == 200
    data = await resp.json()
    assert data == 101
    
@pytest.mark.asyncio
async def test_receive_answer_handler(cli):
    """Test the POST /receive_answer endpoint."""
    resp = await cli.post('/receive_answer')
    assert resp.status == 200
    data = await resp.json()
    assert data == 'OK'

@pytest.mark.asyncio
@mock.patch('app.asyncio.create_task')
@mock.patch('app.leader_election', new_callable=mock.AsyncMock)
async def test_receive_election_starts_election(mock_election, mock_create_task, cli):
    """Test /receive_election starts election when ELECTION_IN_PROCESS is False."""
    
    # 1. Arrange: Ensure the flag is False
    app.ELECTION_IN_PROCESS = False
    
    # 2. Act: Send the request
    resp = await cli.post('/receive_election')
    
    # 3. Assert: Check the results
    assert resp.status == 200
    
    # Check that the global flag was set to True
    assert app.ELECTION_IN_PROCESS == True
    
    # Check that leader_election() was scheduled as a task
    # It checks that create_task was called with the result of leader_election() coroutine
    mock_create_task.assert_called_once()
    mock_election.assert_called_once() # Check the coroutine was instantiated

@pytest.mark.asyncio
@mock.patch('app.asyncio.create_task')
async def test_receive_election_skips_if_election_in_process(mock_create_task, cli):
    """Test /receive_election skips starting a new election if one is running."""
    
    # 1. Arrange: Ensure the flag is True
    app.ELECTION_IN_PROCESS = True
    
    # 2. Act: Send the request
    resp = await cli.post('/receive_election')
    
    # 3. Assert: Check the results
    assert resp.status == 200
    assert app.ELECTION_IN_PROCESS == True # Flag remains True
    
    # Check that the task was NOT created
    mock_create_task.assert_not_called()


@pytest.mark.asyncio
@mock.patch('app.send_broadcast', new_callable=mock.AsyncMock)
@mock.patch('app.send_unicast') # Mocking requests is often complex, using this simple mock for now
async def test_leader_election_becomes_leader(mock_unicast, mock_broadcast):
    """Test case where the pod has the highest ID and becomes the leader."""
    
    # 1. Arrange: Set state for highest ID
    app.POD_ID = 100 
    app.POD_IP = '10.0.0.100'
    app.IP_TO_ID = {'10.0.0.2': 60, '10.0.0.3': 40} # All other IDs are lower
    
    # 2. Act: Run the coroutine directly
    await app.leader_election()
    
    # 3. Assert: Check if it declared itself leader and broadcasted
    assert app.LEADER['id'] == 100
    assert app.LEADER['url'] == '10.0.0.100'
    mock_broadcast.assert_called_once_with('coordinator')
    mock_unicast.assert_not_called()
    assert app.ELECTION_IN_PROCESS == False # Must reset the flag
    
@pytest.mark.asyncio
@mock.patch('app.send_broadcast', new_callable=mock.AsyncMock)
@mock.patch('app.send_unicast') 
async def test_leader_election_higher_id_responds_ok(mock_unicast, mock_broadcast):
    """Test case where a higher ID pod responds 'OK'."""
    
    # 1. Arrange: Set state for a lower ID
    app.POD_ID = 50
    app.IP_TO_ID = {'10.0.0.2': 60, '10.0.0.3': 40} # 60 is a candidate
    
    # Mock the response from the higher ID to simulate an 'OK'
    mock_response = mock.Mock()
    mock_response.cr_code = 200 # Assuming cr_code is the correct attribute for status
    mock_unicast.return_value = mock_response
    
    # 2. Act: Run the coroutine directly
    await app.leader_election()
    
    # 3. Assert: Check if it sent election messages and did NOT become leader
    mock_unicast.assert_called_once() # Should only call 60
    mock_broadcast.assert_not_called() # Should not broadcast coordinator
    assert app.ELECTION_IN_PROCESS == False # Must reset the flag