import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import requests
from requests.sessions import Session

POD_IP = str(os.environ['POD_IP'])
WEB_PORT = int(os.environ['WEB_PORT'])
POD_ID = random.randint(0, 100)

leader = {'id': -1, 'url': ''}
IP_LIST = {}
IP_TO_ID = {}
election_in_progress: bool = False

async def setup_k8s():
    # If you need to do setup of Kubernetes, i.e. if using Kubernetes Python client
	print("K8S setup completed")

async def send_broadcast(msg):
    tasks = []
    s = Session()
    for pod_ip in IP_LIST:
        endpoint = f'/{msg}'
        url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
        task = s.post(url=url, json=msg, timeout = 2)
        tasks.append(task)
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    for resp in responses:
        if isinstance(resp, Exception):
            print(f"Broadcast error: {resp}")

async def send_unicast(msg, pod_ip):
    endpoint = f'/{msg}'
    url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
    response = requests.get(url, timeout=1)
    return response

async def run_bully():
    global IP_LIST, IP_TO_ID, election_in_progress
    while True:
        print("Running bully")
        await asyncio.sleep(5) # wait for everything to be up
        
        # Get all pods doing bully
        ip_list = []
        print("Making a DNS lookup to service")
        response = socket.getaddrinfo("bully-service",0,0,0,0)
        print("Get response from DNS")
        for result in response:
            ip_list.append(result[-1][0])
        ip_list = list(set(ip_list))
        
        # Remove own POD ip from the list of pods
        ip_list.remove(POD_IP)
        print("Got %d other pod ip's" % (len(ip_list)))
        
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        ip_to_id = dict()
        for pod_ip in ip_list:
            try:
                endpoint = '/pod_id'
                url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
                response = requests.get(url, timeout=2)
                ip_to_id[str(pod_ip)] = response.json()
            
            # If a pod is dead
            except requests.exceptions.RequestException as e:
                print(f"Error communicating with pod {pod_ip}: {e}")
            
        # Other pods in network
        IP_LIST = ip_list
        IP_TO_ID = ip_to_id

        print(IP_TO_ID)
        
        # Sleep a bit, then repeat
        await asyncio.sleep(2)

async def leader_election():
    """
        Host an election, whenever a leader is either down or there is a new candidate
    """
    global election_in_progress, leader
    # Try to acquire the lock, if already held by another election, skip
    print("starting election for node", POD_ID)
    # Collect the ID's higher than my own:
    election_candidates = [node_ID for node_ID in IP_TO_ID.values() if node_ID > POD_ID]
    print(f"Node {POD_ID} will send elections to {len(election_candidates)} node")
    # Check if there are no candidates, elect as leader if no candidates
    if len(election_candidates) == 0:
        leader['id'] = POD_ID
        leader['url'] = POD_IP
        await send_broadcast('recieve_coordinator')
        election_in_progress = False
        return

    # If there are candidates call election on them
    ok_recieved = False
    for candidate in election_candidates:
        response = send_unicast(candidate, 'recieve_election')
        if (response is not None and response.cr_code == 200):
            ok_recieved = True
    # we should send all messages out before terminating
    if ok_recieved:
        election_in_progress = False
        return

    # If no 'ok' from higher candidate, you are then leader
    leader['id'] = POD_ID
    leader['url'] = POD_IP
    await send_broadcast('recieve_coordinator')
    election_in_progress = False
    # send broadcasts sends a message for each node in here


#GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)
    
#POST /receive_answer
async def receive_answer(request):
    return web.json_response('OK')

#POST /receive_election
async def receive_election(request):
    # start election in background task
    global election_in_progress
    if not election_in_progress:
        election_in_progress = True
        asyncio.create_task(leader_election())
    return web.json_response('OK')

#POST /receive_coordinator
async def receive_coordinator(request):
    try:
        data = await request.json()
        leader['id'] = data.get('id', POD_ID)
        leader['url'] = data.get('url', POD_IP)
        return web.json_response('OK')
    except Exception as e:
        print(f"Error in recieve_coordinator: {e}")
        return web.json_response('Error', status=500)

async def background_tasks(app):
    task = asyncio.create_task(run_bully())
    yield
    task.cancel()
    await task

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/pod_id', pod_id)
    app.router.add_post('/receive_answer', receive_answer)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='0.0.0.0', port=WEB_PORT)