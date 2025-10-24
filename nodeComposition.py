"""
Composition node class, incompassing all functions not unique to the intial/improved bully algorithm
"""
import threading
import socket
import time
from flask import Flask, request, jsonify
import requests

PORT = 50000

message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING']

class NodeComposition(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_node_alive: bool # Thread class has inbuilt Thread.is_alive()
    leader_id: int
    nodes: list[int]
    messages_count : int

    def __init__ (self, node_id: int):
        super().__init__(daemon=True)
        self.node_id = node_id
        self.is_node_alive = True
        self.leader_id = -1
        self.nodes = []
        self.messages_count = 0
        self.election_lock = threading.Lock()
        self.server_process = None
        self.shutdown_event = threading.Event()

        self.app = Flask(__name__)
        self._setup_routes()

    def run(self):
        """Thread entrypoint: start Flask server"""
        temp_port = PORT + self.node_id
        # Start Flask server for this node

        while(True):
            if temp_port > 65000:
                raise Exception("No free port")
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
        print(f"Shutting down node {self.node_id}")
        
        # Mark as not alive - this will cause the server to reject new requests
        self.is_node_alive = False
        
        # Set shutdown event to signal any waiting operations
        self.shutdown_event.set()

    def _setup_routes(self):
        # Middleware to check if node is alive before handling any request
        @self.app.before_request
        def check_node_alive():
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

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
    def kill_node(self):
        """
            Event that is controlled by the team to un alive a node
        """
        self.is_node_alive = False

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------

    def discovery(self):
        """
            Scan ports to find a thread that is alive
        """
        port = self.discover_peers()
        # now check that node is alive, else we need discovery again
        resp = self.send_uni_cast(port, "BOOTUP")
        while not resp or resp.status_code == 404:
            # do this until you found a living node 
            port = self.discover_peers((port, 65000))
            if port == -1:
                # then no port could be found
                return []
            # else try new port found, check if it's alive
            resp = self.send_uni_cast(port, "BOOTUP")
            if not resp:
                print("something went wrong in send_uni_cast")
                return []
        # The living node should've sent it's known nodes in the body
        data = resp.json()
        node_ids = data['node_ids']
        return [port] + node_ids

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
        # print("port range: ", port_range)

        for port in range(*port_range):
            prt = self.check_port(port)
            if prt and not prt == self.node_id:
                return prt
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
            # self.messages_count += 1
            if node == self.node_id:
                continue

            target_port = node
            url = f'http://localhost:{target_port}/{msg.lower()}'
            message = {"src": self.node_id, "dst": node, "type": msg}

            try:
                # resp = requests.post(url, json=message, timeout=0.5)
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
        # self.messages_count += 1

        assert msg_type in message_identifier, 'message type should be in message_identifiers'
        target_port = int(dst_node_id)
        url = f'http://localhost:{target_port}/{msg_type.lower()}'
        print("url: ", url)
        message = {"src": self.node_id, "dst": dst_node_id}
        if self.node_id == dst_node_id:
            print("fucking idiot")
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
        # except requests.exceptions
