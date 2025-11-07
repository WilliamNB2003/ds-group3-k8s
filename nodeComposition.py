"""
Composition node class, incompassing all functions not unique to the intial/improved bully algorithm
"""
import threading
import socket
import time
import os
import signal
from flask import Flask, request, jsonify
import requests

PORT = 50000

message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING']

class NodeComposition():
    """Node thread, listening when instantiated"""
    node_id: int
    is_node_alive: bool # Thread class has inbuilt Thread.is_alive()
    leader_id: int
    nodes: list[int]
    messages_count : int
    skip_discovery: bool

    def __init__ (self, node_id: int, skip_discovery: bool):
        # super().__init__(daemon=True)
        self.node_id = node_id
        self.skip_discovery = skip_discovery
        self.is_node_alive = True
        self.leader_id = -1
        self.nodes = []
        self.messages_count = 0
        self.election_lock = threading.Lock()
        self.server_process = None
        self.shutdown_event = threading.Event()
        self.shutdown_in_progress = False  # flag to prevent multiple shutdowns

        self.app = Flask(__name__)
        self._setup_routes()

    def run(self):
        """Thread entrypoint: start Flask server"""
        temp_port = PORT + self.node_id
        # Start Flask server for this node
        print(f"node {self.node_id} is booting up")
        while(True):
            if temp_port > 65000:
                # exit out
                print("no available port could be found for node ", self.node_id)
                return
            try:
                print("Trying to find port")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", temp_port))
                print("found port")
                self.node_id = temp_port
                # Run Flask server with threaded=True to handle concurrent requests
                self.app.run(host="127.0.0.1", port=temp_port, debug=False, use_reloader=False, threaded=True)
                break
            except Exception:
                print("new port")
                temp_port += 1

    def shutdown(self):
        """Shutdown this node's Flask server"""
        if self.shutdown_in_progress:
            print(f"Node {self.node_id} shutdown already in progress, skipping...")
            return
            
        self.shutdown_in_progress = True
        print(f"Shutting down node {self.node_id}")
        
        # Mark as not alive immediately
        self.is_node_alive = False
        self.shutdown_event.set()

    def _setup_routes(self):
        # Middleware to check if node is alive before handling any request
        @self.app.before_request
        def check_node_alive():
            # Allow shutdown requests even when node is not alive
            if request.endpoint == 'shutdown':
                return None
            if not self.is_node_alive:
                print("node ", self.node_id, " is not alive..")
                return jsonify({"status": "Not alive"}), 401
            return None

        @self.app.route('/ping', methods=["GET"])
        def ping_end():
            return jsonify({"status": "Alive"}), 200
        
        @self.app.route('/winner', methods=["GET"])
        def winner_end():
            return jsonify({"status": "OK"}), 200
        
        @self.app.route('/bootup', methods=['POST'])
        def bootup_end():
            data = request.get_json()
            src = data.get("src")
            print('Node ', self.node_id, ' recieved a bootup msg from ', src)

            self.new_node(src)
            return jsonify({"leader_id": self.leader_id, "node_ids": self.nodes}), 200
        
        @self.app.route('/coordinator', methods=['PUT'])
        def coordinator_end():
            data = request.get_json()
            
            new_leader = data.get('leader_id')
            # if new_leader == -1:
            # print(f'recieved new leader is -1, from node {src}')
            self.leader_id = int(new_leader)
            print(f'New leader is {int(new_leader)}, {self.node_id}')
            return jsonify({"status": "Acknowledged"}), 200

        @self.app.route('/shutdown', methods=['POST'])
        def shutdown():
            print(f"Shutdown request received for node {self.node_id}")
            
            # Set the shutdown flag
            self.is_node_alive = False
            
            # Use a more graceful shutdown approach
            # Instead of killing the process, use threading to shutdown
            def delayed_shutdown():
                time.sleep(0.1)  # Small delay to let response be sent
                func = request.environ.get('werkzeug.server.shutdown')
                if func is not None:
                    func()
                else:
                    # For newer versions of Werkzeug, we'll set a flag
                    # The Flask server will need to be stopped from outside
                    pass
            
            # Start shutdown in a separate thread
            shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
            shutdown_thread.start()
            
            return jsonify({"status": "Server shutting down"}), 200

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
    def kill_node(self):
        """
            Event that is controlled by the team to un alive a node
        """
        self.is_node_alive = False
        print("------------------------------------------------------")
        print("Node: ", self.node_id, " was killed in NodeComposition")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("======================================================")

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------

    def discovery(self):
        """Scan ports to find a thread that is alive"""
        if self.skip_discovery:
            return []
        port = self.discover_peers()
        if port == -1:
            return []
        print("port was not -1")
        # Try multiple times to find a responsive node
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                resp = self.send_uni_cast(port, "BOOTUP")
                if resp and resp.status_code == 200:
                    data = resp.json()
                    node_ids = data['node_ids']
                    return [port] + node_ids
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for port {port}: {e}")
            
            # Try next available port
            port = self.discover_peers((port + 1, 65000))
            if port == -1:
                break
        
        return []

    def check_port(self, port):
        """Quick check if a Flask app is running on this port"""
        try:
           sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           sock.settimeout(0.1)  # 100ms timeout
           result = sock.connect_ex(('localhost', port))
           sock.close()
           return port if result == 0 else None
        except socket.error:
           return None


    def discover_peers(self, port_range=(50000, 65000)):
        """Parallel port scan"""
        print("discovery for node", self.node_id)
        for port in range(*port_range):
            print("checking port: ", port)
            prt = self.check_port(port)
            if prt and not prt == self.node_id:
                print("self.node is", self.node_id)
                print("found port ", prt, "wchic is up")
                return prt
        print("could not find any peers")
        return -1

    def new_node(self, node_id):
        """
            Whenever a bootup is registered we check if a new node should be appended to the list
        """
        if not node_id in self.nodes:
            self.nodes.append(node_id)



    def send_broadcast(self, msg: str) -> list[requests.Response]:
        """
            Sending a message to all nodes in the node list
        """
        # For every node, send an http request with msg
        responses = []
        for node in self.nodes:
            if node == self.node_id:
                continue

            target_port = node
            url = f'http://localhost:{target_port}/{msg.lower()}'
            message = {"src": self.node_id, "dst": node, "type": msg}

            try:
                resp = ''
                if msg == 'COORDINATOR':
                    # this endpoint retrives
                    message = {"src": self.node_id, "dst": node, 'leader_id': self.leader_id}
                    resp =  requests.put(url, json=message, timeout=0.5)
                elif msg == 'BOOTUP':
                    print("sending bootup, " , url)
                    resp =  requests.post(url, json=message, timeout=0.5)
                else:
                    resp =  requests.get(url, json=message, timeout=0.5)

                responses.append(resp)
            except requests.exceptions.ConnectionError as e:
                print(f'Error occurred whilst sending broadcast to node {node}, error was: {e}')
                continue
            # except Co
        return responses

    def send_uni_cast(self, dst_node_id: int, msg_type: str):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        print("node", self.node_id, " sending to port: ", dst_node_id)

        assert msg_type in message_identifier, 'message type should be in message_identifiers'
        target_port = int(dst_node_id)
        url = f'http://localhost:{target_port}/{msg_type.lower()}'
        print("url: ", url)
        message = {"src": self.node_id, "dst": dst_node_id}
        if self.node_id == dst_node_id:
            return
        
        try:
            if msg_type == 'COORDINATOR':
                return requests.put(url, json=message, timeout=0.5)
            elif msg_type == 'BOOTUP':
                return requests.post(url, json=message, timeout=0.5)
            else:
                return requests.get(url, json=message, timeout=0.5)

        except requests.exceptions.ConnectionError as e:
            print(f'Error occurred whilst unicasting to node {dst_node_id}, error. {e}')
            return None
