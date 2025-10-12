"""Initial Bully algorithm implementation

    Returns:
        _type_: _description_
"""
import threading
import time
from flask import jsonify
from nodeComposition import NodeComposition

PORT = 50000 # Port 50000 is broadcast and 50001 is node 1 etc...
message_identifier = ['COORDINATOR', 'BOOTUP', 'ELECTION', 'PING']

class Node(NodeComposition):
    """Node thread, listening when instantiated"""

    def __init__ (self, node_id: int):
        super().__init__(node_id, daemon=True)

    def start_node(self):
        """Start Flask server in thread, then bootup after it's ready"""
        self.start()            # starts the Flask server in background thread
        time.sleep(0.1)           # give server time to bind to port
        self.bootup()           # now safe to send HTTP requests

    def _setup_routes(self):
        # First call parent's _setup_routes to get all base routes
        super()._setup_routes()
        
        @self.app.route('/election', methods=["GET"])
        def election_end():
            if self.election_lock.acquire(blocking=False):
                threading.Thread(target=self.election, daemon=True).start()
            return jsonify({"status": "OK"}), 200

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
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
        time.sleep(0.2)
        response = self.send_uni_cast(self.leader_id, "PING")
        if response is None or not (response.status_code == 200):
            self.nodes.pop()
            if self.election_lock.acquire(blocking=False):
                threading.Thread(target=self.election, daemon=True).start()
            return

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------
    def bootup(self):
        """
            Broadcasts to all other nodes that this node exists, so they update their table
        """
        print("discovery: node id: ", self.node_id)
        node_ids = self.discovery()
        self.nodes = self.nodes + node_ids
        print("cuurent knoiwn nodes: ", self.nodes, " for node ", self.node_id)
        responses = self.send_broadcast('BOOTUP')

        # Update the leader ID for the booted up node
        if len(responses) == 0:
            if self.election_lock.acquire(blocking=False):
                threading.Thread(target=self.election, daemon=True).start()

        for response in responses:
            data = response.json()
            if response and response.status_code == 200:
                self.leader_id = max(self.leader_id, int(data["status"]))
                break

        if self.leader_id < self.node_id:
            if self.election_lock.acquire(blocking=False):
                threading.Thread(target=self.election, daemon=True).start()

    def election(self):
        """
            Host an election, whenever a leader is either down or there is a new candidate
        """
        try:
            # Collect the ID's higher than my own:
            election_candidates = [node for node in self.nodes if (node > self.node_id)]
            print(f"Node {self.node_id} send election to {len(election_candidates)} node")
            # Check if there are no candidates, elect self as leader if no candidates
            if len(election_candidates) == 0:
                self.leader_id = self.node_id
                self.send_broadcast('COORDINATOR')
                return

            # If there are candidates call election on them
            for candidate in election_candidates:
                response = self.send_uni_cast(candidate, 'ELECTION')
                # If there is just 1 response, then don't do anything
                if (response is not None and response.status_code == 200):
                    return

            # If no 'ok' from higher candidate, you are then leader
            self.leader_id = self.node_id
            self.send_broadcast('COORDINATOR')
            self.is_leader = True
        finally:
            self.election_lock.release()
