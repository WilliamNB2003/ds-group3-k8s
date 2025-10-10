"""Node class acts as independent node

    Returns:
        _type_: _description_
"""
import threading
import time
from flask import Flask, request, jsonify
import requests

PORT = 30000 # Port 50000 is broadcast and 50001 is node 1 etc...
message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING', 'WINNER']

class Node(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_node_alive: bool # Thread class has inbuilt Thread.is_alive()
    is_leader: bool
    leader_id: int
    nodes: list[int]
    messages_count : int


    def __init__ (self, node_id: int, nodes: list[int]):
        super().__init__()
        self.node_id = node_id
        self.is_node_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes
        self.messages_count = 0
        

        self.app = Flask(__name__)
        self._setup_routes()

    def run(self):
        """Thread entrypoint: start Flask server"""
        port = PORT + self.node_id
        # Start Flask server for this node
        while(True):
            if port > 65000:
                break
            else:
                try:
                    self.app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
                    break
                except SystemExit:
                    port += 1


    def start_node(self):
        """Start Flask server in thread, then bootup after it's ready"""
        self.start()            # starts the Flask server in background thread
        time.sleep(0.1)           # give server time to bind to port
        self.bootup()           # now safe to send HTTP requests

    def _setup_routes(self):
        # Middleware to check if node is alive before handling any request
        @self.app.before_request
        def check_node_alive():
            if not self.is_node_alive:
                return jsonify({"status": "Not alive"}), 401

        @self.app.route('/election', methods=["GET"])
        def election_end():

            return jsonify({"status": "OK"}), 200

        @self.app.route('/ping', methods=["GET"])
        def ping_end():
            return jsonify({"status": "Alive"}), 200
        
        @self.app.route('/winner', methods=["GET"])
        def winner_end():
            return jsonify({"status": "OK"}), 200
        
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
        
        @self.app.route('/bootup', methods=['POST'])
        def bootup_end():
            data = request.get_json()
            src = data.get("src")

            self.new_node(src)
            return jsonify({"status": self.leader_id}), 200

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
    def kill_node(self):
        """
            Event that is controlled by the team to un alive a node
        """
        self.is_node_alive = False

    def revive_node(self):
        """
            Event that is controlled by the team to revive a node
        """
        self.is_node_alive = True
        self.bootup()

    def ping_leader(self):
        """
            Check if leader is alive
        """
        response = self.send_uni_cast(self.leader_id, "PING")
        if response is None or not (response.status_code == 200):
            self.nodes.pop()
            self.election()
            return
        # print('Leader is still alive: ', response.status_code)

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------
    def bootup(self):
        """
            Broadcasts to all other nodes that this node exists, so they update their table
        """
        # print("-------------- Node: ", self.node_id, " is trying to bootup... --------------")
        responses = self.send_broadcast('BOOTUP')

        # Update the leader ID for the booted up node
        if len(responses) == 0:
            self.election()

        for response in responses:
            data = response.json()
            if response and response.status_code == 200:
                self.leader_id = int(data["status"])
                # print(f'found my leader: {self.leader_id}')
                break

        if self.leader_id < self.node_id:
            # print(f'Me node {self.node_id} is running nnew election')
            self.election()

        # print(f'node {self.node_id} booted up..')

    def new_node(self, node_id):
        """
            Whenever a bootup is registered we check if a new node should be appended to the list
        """
        if not node_id in self.nodes:
            self.nodes.append(node_id)

    def resetMessageCount(self):
        self.messages_count = 0

    def election(self):
        """
            Host an election, whenever a leader is either down or there is a new candidate
        """
        # print(f'Node {self.node_id} is starting new election')
        # Collect the ID's higher than my own:
        election_candidates = [node for node in self.nodes if (node > self.node_id)]
        # print(election_candidates, len(election_candidates) == 0)
        # Check if there are no candidates, elect self as leader if no candidates
        if len(election_candidates) == 0:
            # print("Election candidates: ", election_candidates)
            self.send_broadcast('COORDINATOR', self.node_id)
            self.leader_id = self.node_id
            # print(f"Leader is now {self.leader_id}")
            return

        # If there are candidates call election on them
        highest_id = -1
        for candidate in election_candidates:
            response = self.send_uni_cast(candidate, 'ELECTION')
            # print('send election to candidate ', candidate)
            if (response is not None and response.status_code == 200):
                if highest_id < candidate:
                    highest_id = candidate
        
        if highest_id > self.node_id:
            # this candidate is now leader
            
            self.send_broadcast('COORDINATOR', highest_id)
            return

        # If no 'ok' from higher candidate, you are then leader
        self.send_broadcast('COORDINATOR', self.node_id)
        self.is_leader = True
        self.leader_id = self.node_id

    def send_broadcast(self, msg: str, new_leader = -2) -> list[requests.Response]:
        """
            Sending a message to all nodes in the node list
        """
        # For every node, send an http request with msg
        responses = []
        for node in self.nodes:
            self.messages_count += 1
            if node == self.node_id:
                continue

            target_port = PORT + node
            url = f'http://localhost:{target_port}/{msg.lower()}'
            message = {"src": self.node_id, "dst": node, "type": msg, 'leader_id': new_leader}

            try:
                # resp = requests.post(url, json=message, timeout=0.5)
                resp = ''
                if msg == 'COORDINATOR':
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
        target_port = PORT + int(dst_node_id)
        url = f'http://localhost:{target_port}/{msg_type.lower()}'

        message = {"src": self.node_id, "dst": dst_node_id, "type": msg_type}

        try:
            if msg_type == 'COORDINATOR':
                return requests.put(url, json=message, timeout=0.5)
            elif msg_type == 'BOOTUP':
                return requests.post(url, json=message, timeout=0.5)
            else:
                return requests.get(url, json=message, timeout=0.5)

        except requests.exceptions.ConnectionError:
            # print(f'Error occurred whilst unicasting to node {dst_node_id}')
            return None
        # except requests.exceptions
