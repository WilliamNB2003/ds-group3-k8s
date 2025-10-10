"""Node class acts as independent node

    Returns:
        _type_: _description_
"""
import threading
from flask import Flask, request, jsonify
import requests
import socket

PORT = 50000 # Port 30000 is broadcast and 30001 is node 1 etc...
message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING']

class NodeComposition(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_node_alive: bool # Thread class has inbuilt Thread.is_alive()
    is_leader: bool
    leader_id: int
    nodes: list[int]
    messages_count : int
    has_found_port: bool
    port: int

    def __init__ (self, node_id: int, nodes: list[int], daemon: bool):
        super().__init__(daemon=daemon)
        self.node_id = node_id
        self.is_node_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes
        self.messages_count = 0
        self.election_lock = threading.Lock()
        self.has_found_port = False

        self.app = Flask(__name__)
        self._setup_routes()

    def run(self):
        """Thread entrypoint: start Flask server"""
        temp_port = PORT + self.node_id
        # Start Flask server for this node
        while(True):
            if temp_port > 65000:
                raise Exception("No free port")
            else:
                try:
                    print("Trying to find port")
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(("127.0.0.1", temp_port))
                    print("found port")
                    self.node_id = temp_port
                    self.has_found_port = True
                    self.app.run(host="127.0.0.1", port=temp_port, debug=True, use_reloader=False)
                    break
                except Exception:
                    print("noew port")
                    temp_port += 1


    def _setup_routes(self):
        # Middleware to check if node is alive before handling any request
        @self.app.before_request
        def check_node_alive():
            if not self.is_node_alive:
                return jsonify({"status": "Not alive"}), 401

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

            self.new_node(src)
            return jsonify({"status": self.leader_id}), 200
        
        @self.app.route('/coordinator', methods=['PUT'])
        def coordinator_end():
            data = request.get_json()
            
            new_leader = data.get('leader_id')
            # if new_leader == -1:
            # print(f'recieved new leader is -1, from node {src}')
            self.leader_id = int(new_leader)
            self.is_leader = False
            # print(f'New leader is {int(src)}, {self.node_id}')
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
    def new_node(self, node_id):
        """
            Whenever a bootup is registered we check if a new node should be appended to the list
        """
        if not node_id in self.nodes:
            self.nodes.append(node_id)

    def resetMessageCount(self):
        self.messages_count = 0

    def send_broadcast(self, msg: str) -> list[requests.Response]:
        """
            Sending a message to all nodes in the node list
        """
        # For every node, send an http request with msg
        responses = []
        for node in self.nodes:
            self.messages_count += 1
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
                    message = {"src": self.node_id, "dst": node, "type": msg, 'leader_id': self.node_id}
                    resp =  requests.put(url, json=message, timeout=0.5)
                elif msg == 'BOOTUP':
                    resp =  requests.post(url, json=message, timeout=0.5)
                else:
                    resp =  requests.get(url, json=message, timeout=0.5)

                responses.append(resp)
            except requests.exceptions.ConnectionError:
                # print(f'Error occurred whilst sending broadcast to node {node}')
                continue
            # except Co
        return responses

    def send_uni_cast(self, dst_node_id: int, msg_type: str):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        self.messages_count += 1

        assert msg_type in message_identifier, 'message type should be in message_identifiers'
        target_port = int(dst_node_id)
        url = f'http://localhost:{target_port}/{msg_type.lower()}'

        message = {"src": self.node_id, "dst": dst_node_id, "type": msg_type}
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

        except ConnectionError:
            # print(f'Error occurred whilst unicasting to node {dst_node_id}')
            return None
        # except requests.exceptions