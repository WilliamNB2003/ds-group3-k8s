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
import cookies
from kubernetes import client, config

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


async def setup_k8s():
    # If you need to do setup of Kubernetes, i.e. if using Kubernetes Python client
	print("K8S setup completed")

async def send_coordinator():
    tasks = []
    s = Session()
    data = json.dumps({'id': POD_ID, 'url': POD_IP})
    for pod_ip in IP_LIST:
        endpoint = '/recieve_election'
        url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
        task = s.post(url=url, data=data, timeout = 2)
        tasks.append(task)
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    for resp in responses:
        if isinstance(resp, Exception):
            print(f"Broadcast error: {resp}")

async def send_election():
    tasks = []
    s = Session()
    ip_list = [ip for ip in IP_LIST if IP_TO_ID[ip] > POD_ID]
    for pod_ip in ip_list:
        endpoint = '/recieve_election'
        url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
        task = s.post(url=url, timeout = 2)
        tasks.append(task)
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    return responses

async def heartbeat():
    global IP_LIST, IP_TO_ID, ELECTION_IN_PROCESS, leader
    while True:
       
        await asyncio.sleep(5) # wait for everything to be up
        print("Starting heartbeat")
        
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
        print(f"Got {len(ip_list)} other pod ip's")

        # current leader
        current_leader = leader # copy or smth
        leader_found = False
        call_election = True
        
        # Get ID's of other pods by sending a GET request to them
        await asyncio.sleep(random.randint(1, 5))
        ip_to_id = {}
        for pod_ip in ip_list:
            try:
                endpoint = '/pod_id'
                url = 'http://' + str(pod_ip) + ':' + str(WEB_PORT) + endpoint
                response = requests.get(url, timeout=2)
                crnt_pod_id = response.json()
                # check for leader
                if crnt_pod_id == current_leader["id"]:
                    leader_found = True
                if crnt_pod_id > current_leader["id"]:
                    # a new leader has been found?
                    call_election = True
                    
                # else we don't care
                ip_to_id[str(pod_ip)] = int(crnt_pod_id)
            # If a pod is dead
            except requests.exceptions.RequestException as e:
                print(f"Error communicating with pod {pod_ip}: {e}")

        
        # Other pods in network
        IP_LIST = ip_list
        IP_TO_ID = ip_to_id
        # after requesting every found pod
        if not leader_found or call_election:
            await leader_election()
        
        print("="*50)
        print(IP_TO_ID)

async def leader_election():
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
        label_self_as_leader()
        return

    # If there are candidates call election on them
    ok_recieved = False
    responses = send_election()
    for response in responses:
        if (response is not None and response.cr_code == 200):
            ok_recieved = True
    # we should send all messages out before terminating
    if ok_recieved:
        ELECTION_IN_PROCESS = False
        remove_leader_label()
        return

    # If no 'ok' from higher candidate, you are then leader
    leader['id'] = POD_ID
    leader['url'] = POD_IP
    # send broadcasts sends a message for each node in here
    await send_coordinator()
    ELECTION_IN_PROCESS = False
    return


#GET /pod_id
async def pod_id(request):
    return web.json_response(POD_ID)

#POST /receive_answer
async def receive_answer(request):
    return web.json_response('OK')

#POST /receive_election
async def receive_election(request):
    # start election in background task
    global ELECTION_IN_PROCESS
    if not ELECTION_IN_PROCESS:
        ELECTION_IN_PROCESS = True
        asyncio.create_task(leader_election())
    return web.json_response('OK')

#POST /receive_coordinator
async def receive_coordinator(request):
    try:
        data = await request.json()
        leader['id'] = data.get('id', POD_ID)
        leader['url'] = data.get('url', POD_IP)
        remove_leader_label()
        return web.json_response('OK')
    except Exception as e:
        print(f"Error in recieve_coordinator: {e}")
        return web.json_response('Error', status=500)
    
async def get_cookie():
    return web.json_response(random.choice(cookies.cookiesList))

def label_self_as_leader():
    # The patch to apply
    body = {
        "metadata": {
            "labels": {
                "role": "leader"
            }
        }
    }
    # Patch the pod
    v1.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
    print(f"Labeled pod {pod_name} as leader")

def remove_leader_label():
    # Remove label by setting it to None
    body = {
        "metadata": {
            "labels": {
                "role": None
            }
        }
    }
    v1.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
    print(f"Removed leader label from pod {pod_name}")

async def background_tasks(app):
    task = asyncio.create_task(heartbeat())
    yield
    task.cancel()
    await task

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get('/pod_id', pod_id)
    app.router.add_get('/get_cookie', get_cookie)
    app.router.add_post('/receive_answer', receive_answer)
    app.router.add_post('/receive_election', receive_election)
    app.router.add_post('/receive_coordinator', receive_coordinator)
    app.cleanup_ctx.append(background_tasks)
    web.run_app(app, host='0.0.0.0', port=WEB_PORT)