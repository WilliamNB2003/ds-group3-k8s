import asyncio
from aiohttp import web
import os
import socket
import random
import aiohttp
import requests
from requests.sessions import Session
import json
import hashlib
from cookies import cookiesList
from frontend import frontpage_html
from kubernetes import client, config
from aiohttp import ClientSession, ClientTimeout, ClientResponse
from asyncio import create_task
import pathlib

config.load_incluster_config()
v1 = client.CoreV1Api()

pod_name = os.environ['POD_NAME']
namespace = os.environ.get('NAMESPACE', 'default')

POD_IP = str(os.environ['POD_IP'])
WEB_PORT = int(os.environ['WEB_PORT'])
hostname = socket.gethostname()
POD_ID = int(hashlib.md5(hostname.encode()).hexdigest(), 16) % 10**6

leader = {'id': -1, 'url': ''}
IP_LIST = {}
IP_TO_ID = {}
ELECTION_IN_PROCESS: bool = False
IS_READY = True

# Add this new endpoint
async def readiness_check(request):
    """Return 200 only if ready to serve traffic"""
    if IS_READY:
        return web.Response(status=200, text="OK")
    else:
        return web.Response(status=503, text="Not Ready")
    
async def setup_k8s():
    # If you need to do setup of Kubernetes, i.e. if using Kubernetes Python client
	print("K8S setup completed")

async def send_coordinator():
    tasks = []
    payload = {'id': POD_ID, 'url': POD_IP}
    async with ClientSession(timeout=ClientTimeout(total=2)) as session:

        for pod_ip in IP_LIST:
            endpoint = '/receive_coordinator'
            url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
            task = create_task(session.post(url=url, json=payload))
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for resp in responses:
            if isinstance(resp, Exception):
                print(f"Broadcast error: {resp}")

async def send_election():
    tasks = []
    ip_list = [ip for ip in IP_LIST if IP_TO_ID[ip] > POD_ID]
    async with ClientSession(timeout=ClientTimeout(total=2)) as session:
        for pod_ip in ip_list:
            endpoint = '/receive_election'
            url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
            task = create_task(session.post(url=url))
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return responses

async def heartbeat():
    global IP_LIST, IP_TO_ID, ELECTION_IN_PROCESS, leader
    while True:
       
        await asyncio.sleep(1) # wait for everything to be up
        print("Starting heartbeat")
        
        # Get all pods doing bully
        ip_list = []
        print("Making a DNS lookup to service")
        response = await asyncio.to_thread(socket.getaddrinfo, "bully-service", 0, 0, 0, 0)
        print("Get response from DNS")
        for result in response:
            ip_list.append(result[-1][0])
        ip_list = list(set(ip_list))
        
        # Remove own POD ip from the list of pods
        ip_list.remove(POD_IP)
        print(f"Got {len(ip_list)} other pod ip's")

        # current leader
        current_leader = leader # copy or smth
        leader_found = leader['id'] == POD_ID
        call_election = False
        
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.uniform(0.1, 0.5))
        ip_to_id = {}
        async with ClientSession(timeout=ClientTimeout(total=0.5)) as session:
            tasks = []
            for pod_ip in ip_list:
                endpoint = '/pod_id'
                url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
                task = create_task(session.get(url=url))
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for id, response in enumerate(responses):
                pod_ip = ip_list[id]
                try:
                    if isinstance(response, ClientResponse) and response.status == 200:
                        crnt_pod_id = await response.json()
                        # check for leader
                        if crnt_pod_id == current_leader["id"]:
                            leader_found = True
                        if crnt_pod_id > current_leader["id"]:
                            # a new leader has been found?
                            call_election = True
                            
                        # else we don't care
                        ip_to_id[str(pod_ip)] = int(crnt_pod_id)
                # If a pod is dead
                except aiohttp.ClientError as e:
                    print(f"Error communicating with pod {pod_ip}: {e}")

        # Other pods in network
        IP_LIST = ip_list
        IP_TO_ID = ip_to_id
        # after requesting every found pod
        if not leader_found or call_election:
            await general_election()
        
        print("="*50)
        print(IP_TO_ID)
        print("Leader ID: " + str(leader["id"]))

        if leader['id'] != -1 and leader['id'] != POD_ID:
            await remove_leader_label()

async def leader_election():
    """
        Host an election, whenever a leader is either down or there is a new candidate
    """
    global ELECTION_IN_PROCESS, leader, ELECTION_TYPE
    # Try to acquire the lock, if already held by another election, skip
    print("starting election for node", POD_ID)
    if ELECTION_IN_PROCESS:
        print("[LEADER_ELECTION] Already in progress, skipping ...")
        return
    ELECTION_IN_PROCESS = True
    # Collect the ID's higher than my own:
    election_candidates = [node_ID for node_ID in IP_TO_ID.values() if node_ID > POD_ID]
    print(f"Node {POD_ID} will send elections to {len(election_candidates)} nodes")
    # Check if there are no candidates, elect as leader if no candidates
    if len(election_candidates) == 0:
        leader['id'] = POD_ID
        leader['url'] = POD_IP
        await send_coordinator()
        ELECTION_IN_PROCESS = False
        await label_self_as_leader()
        return

    # If there are candidates call election on them
    ok_recieved = False
    responses = await send_election()
    for response in responses:
        if isinstance(response, ClientResponse) and response.status == 200:
            ok_recieved = True
        else:
            print(f"Broadcast error: {response}")

    # we should send all messages out before terminating
    if ok_recieved:
        ELECTION_IN_PROCESS = False
        
        was_leader = (leader['id'] == POD_ID)
        await remove_leader_label()
        
        if was_leader:
            print(f"Stepping down: Found higher candidate. Restarting to break sticky connections.")
            asyncio.get_event_loop().call_later(1, lambda: os._exit(0))
            
        return

    # If no 'ok' from higher candidate, you are then leader
    leader['id'] = POD_ID
    leader['url'] = POD_IP
    # send broadcasts sends a message for each node in here
    await send_coordinator()
    ELECTION_IN_PROCESS = False
    return

async def improved_leader_election():
    """
        Host an election, whenever a leader is either down or there is a new candidate
    """
    global ELECTION_IN_PROCESS, leader
    # Try to acquire the lock, if already held by another election, skip
    print("starting election for node", POD_ID)
    if ELECTION_IN_PROCESS:
        print("[LEADER_ELECTION] Already in progress, skipping ...")
        return
    ELECTION_IN_PROCESS = True
    # Collect the ID's higher than my own:
    election_candidates = [node_ID for node_ID in IP_TO_ID.values() if node_ID > POD_ID]
    print(f"Node {POD_ID} will send elections to {len(election_candidates)} nodes")
    # Check if there are no candidates, elect as leader if no candidates
    if len(election_candidates) == 0:
        leader['id'] = POD_ID
        leader['url'] = POD_IP
        await send_coordinator()
        ELECTION_IN_PROCESS = False
        await label_self_as_leader()
        return

    # If there are candidates call election on them
    ok_recieved = False
    highest_id = -1
    responses = await send_election()
    for response in responses:
        if isinstance(response, ClientResponse) and response.status == 200:
            ok_recieved = True
            # highest_id = max(highest_id, )
        else:
            print(f"Broadcast error: {response}")

    # we should send all messages out before terminating
    if ok_recieved:
        ELECTION_IN_PROCESS = False
        await remove_leader_label()
        return

    # If no 'ok' from higher candidate, you are then leader
    leader['id'] = POD_ID
    leader['url'] = POD_IP
    # send broadcasts sends a message for each node in here
    await send_coordinator()
    ELECTION_IN_PROCESS = False
    return

async def label_self_as_leader():
    # The patch to apply
    body = { "metadata": { "labels": { "role": "leader" } } }
    print(f"Labeled pod {pod_name} as leader with id {POD_ID}")
    # Patch the pod
    await asyncio.to_thread(v1.patch_namespaced_pod, name=pod_name, namespace=namespace, body=body)

async def remove_leader_label():
    # Remove label by setting it to None
    body = {"metadata": {"labels": {"role": None}}}
    print(f"Removed leader label from pod {pod_name}")

    await asyncio.to_thread(v1.patch_namespaced_pod, name=pod_name, namespace=namespace, body=body)

async def general_election():
    # start election in background task
    ELECTION_TYPE = os.getenv('ELECTION_TYPE')
    print(f"Server uses ELECTION_TYPE: {ELECTION_TYPE}")
    if (ELECTION_TYPE == 'normal'):
        asyncio.create_task(leader_election())
    elif (ELECTION_TYPE == 'improved'):
        asyncio.create_task(improved_leader_election())
    else:
        print("Not recognized ELECTION_TYPE, defaulting to normal")
        asyncio.create_task(leader_election())

#GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)

#POST /receive_answer
async def receive_answer(request):
    return web.json_response('OK')

#POST /receive_election
async def receive_election(request):
    await general_election()
    return web.json_response('OK')

#POST /receive_coordinator
async def receive_coordinator(request):
    global IS_READY
    try:
        data = await request.json()
        
        was_leader = (leader['id'] == POD_ID)
        
        leader['id'] = data.get('id', POD_ID)
        leader['url'] = data.get('url', POD_IP)
        await remove_leader_label()
        
        if was_leader and leader['id'] != POD_ID:
            print(f"Stepping down: Marking as not ready immediately")
            IS_READY = False  # Fail readiness checks immediately
            asyncio.get_event_loop().call_later(1, lambda: os._exit(0))

        return web.json_response('OK')
    except Exception as e:
        print(f"Error in recieve_coordinator: {e}")
        return web.json_response('Error', status=500)
        
async def get_cookie(request):    
    cookie = random.choice(cookiesList)
    cookie += " Pod ID: " + str(POD_ID) + " and leader is: " + str(leader["id"])
    return web.json_response(cookie)
        

async def background_tasks(app):
    task = asyncio.create_task(heartbeat())
    yield
    task.cancel()
    await task

async def homepage(request):
    return web.Response(text=frontpage_html, content_type='text/html')

static_dir = pathlib.Path(__file__).resolve().parent / 'static'

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/', homepage)
    app.router.add_static('/static/', path=str(static_dir), name='static')

    app.router.add_get('/pod_id', pod_id)
    app.router.add_get('/readiness', readiness_check)
    app.router.add_get('/get_cookie', get_cookie)
    app.router.add_post('/receive_answer', receive_answer)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='0.0.0.0', port=WEB_PORT)