import time
import threading
from flask import Flask, request, jsonify
from msg_class import Msg
import requests

BROADCAST_PORT = 50000 # Port 50000 is broadcast and 50001 is node 1 etc...
TIME_DELAY = 5
TIMER_INTERVAL = 0.1
message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING']

class Node(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_node_alive: bool # Thread class has inbuilt Thread.is_alive()
    is_leader: bool
    leader_id: int
    nodes: list[int]
    has_received_ping_reply: tuple[bool, float]
    ongoing_election: bool
    election_time_check: float


    def __init__ (self, node_id: int, nodes: list[int]):
        super().__init__()
        self.node_id = node_id
        self.is_node_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes
        self.has_received_ping_reply = (False, 0)
        self.ongoing_election = False

        self.app = Flask(__name__)
        self._setup_routes()

        # Broadcast
        self.bootup()
        
        # main loop
        self.run()

    def _setup_routes(self):
        @self.app.route("/unicast", methods=["POST"])
        def unicast():
            data = request.get_json()
            src = data.get("src")
            dst = data.get("dst")
            msg_type = data.get("type")
            payload = data.get("payload")

            if msg_type == "ELECTION":
                self.election()
            elif msg_type == "PING":
                if (self.is_node_alive):
                    return 200
                else:
                    return 500

                if payload == "request" and self.is_node_alive:
                    self.send_uni_cast(src, "PING", "reply")
                elif payload == "reply":
                    self.has_received_ping_reply = (True, time.time() + 3)
                

            # Example: return a JSON response
            return jsonify({"status": "OK"}), 200
        
        @self.app.route("/broadcast", methods=["POST"])
        def broadcast():
            data = request.get_json()
            
            src = data.get("src")
            dst = data.get("dst")
            msg_type = data.get("type")
            payload = data.get("payload")

            if msg_type == "COORDINATOR":
                self.leader_id = int(payload)
                self.is_leader = (self.leader_id == self.node_id)
            elif msg_type == "BOOTUP":
                self.new_node(src)
                if self.is_node_alive:
                    return jsonify({"status": "BOOTUP_RESPONSE", "Current_leader": self.leader_id}), 200
            

            # Example: return a JSON response
            return jsonify({"status": "Success"}), 200
            
        

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
        self.has_received_ping_reply = (True, time.time() + 3)
        self.send_uni_cast(self.leader_id, "PING", "request")
        
    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------
    def bootup(self):
        """
            Broadcasts to all other nodes that this node exists, so they update their table
        """
        self.send_broadcast('BOOTUP')
        print(f'node {self.node_id} booted up..')

    def new_node(self, node_id):
        """
            Whenever a bootup is registered we check if a new node should be appended to the list
        """
        if (not (node_id in self.nodes)):
            self.nodes.append(node_id)

    def election(self):
        """
            Host a election, whenever a leader is either down or there is a new candidate
        """

        # Collect the ID's higher than my own:
        election_candidates = []
        for node in self.nodes:
            if (node > self.node_id):
                election_candidates.append(node)
        
        # Check if there are no candidates, elect self as leader if no candidates
        if (len(election_candidates) == 0):
            self.send_broadcast('COORDINATOR')
            return

        # If there are candidates call election on them
        ok_received = False
        for candidate in election_candidates:
            ok_received = ok_received or self.send_uni_cast(candidate, 'ELECTION')

        if (not ok_received):
            self.send_broadcast('COORDINATOR')


    def run(self):
        """Main loop, keeps listening on port 50000 + node_id"""

        while True: 
            if self.has_recieved_ok:
                self.check_queue()
                self.check_ping()

            server_ready = select.select([server_socket], [], [], TIMER_INTERVAL)
            broadcast_ready = select.select([broadcast_socket], [], [], TIMER_INTERVAL)

            if server_ready:
                self.check_queue(server_socket)
            elif broadcast_ready:
                self.handle_broadcast(broadcast_ready)
            else:
                # now check for timers expired
                pass


    def send_broadcast(self, msg_type: str, payload: str = ''):
        assert msg_type in message_identifier, "message type should be in message_identifier"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', int(BROADCAST_PORT)))
            message = Msg(self.node_id, BROADCAST_PORT, msg_type, payload)
            s.sendall(message.format())
            # data_rec = s.recv(512) # Line to recieve data


    def send_uni_cast(self, dst_node_id: int, msg_type: str, payload: str = ''):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        assert msg_type in message_identifier, 'message type should be in message_identifiers'
        target_port = 50000 + int(dst_node_id)
        url = f'http://localhost:{target_port}/unicast'

        message = {"src": self.node_id, "dst": dst_node_id, "type": msg_type, "payload": str(payload)}
        
        try:
            resp = requests.post(url, json=message, timeout=2.0)
            resp.raise_for_status()
            return True
        except requests.Timeout:
            print(f"Timeout when sending to node {dst_node_id}")
            return False
        except requests.ConnectionError:
            print(f"Connection error when sending to node {dst_node_id}")
            return False
        except requests.HTTPError as e:
            print(f"HTTP error when sending to node {dst_node_id}: {e}")
            return False


        return True