"""
Initial Bully algorithm implementation
"""
import threading
from flask import jsonify
from nodeComposition import NodeComposition

class Node(NodeComposition):
    """Node thread, listening when instantiated"""
    messages_lock: threading.Lock

    def __init__ (self, node_id: int):
        super().__init__(node_id)
        self.messages_lock = threading.Lock()

    def start_node(self):
        """Start Flask server in thread, then bootup after it's ready"""
        self.start()
        self.bootup()

    def _setup_routes(self):
        # First call parent's _setup_routes to get all base routes
        super()._setup_routes()
        
        @self.app.route('/election', methods=["GET"])
        def election_end():
            self.increment_messages()
            threading.Thread(target=self.election, daemon=True).start()
            return jsonify({"status": "OK"}), 200

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
    def reset_message_count(self):
        with self.messages_lock:
            self.messages_count = 0
    
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
            # if no response, start election - let election() handle locking
            threading.Thread(target=self.election, daemon=True).start()

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------
    def increment_messages(self, amount = 1):
        with self.messages_lock:
            self.messages_count += amount
    
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
            self.election()

        for response in responses:
            data = response.json()
            if response and response.status_code == 200:
                self.leader_id = max(self.leader_id, int(data["leader_id"]))
                break

        if self.leader_id < self.node_id:
            self.election()

    def election(self):
        """
            Host an election, whenever a leader is either down or there is a new candidate
        """
        # Try to acquire the lock, if already held by another election, skip
        if not self.election_lock.acquire(blocking=False):
            print(f"Node {self.node_id}: Election already in progress, skipping")
            return
        print("starting election for node", self.node_id)
        try:
            # Collect the ID's higher than my own:
            election_candidates = [node for node in self.nodes if node > self.node_id]
            print(f"Node {self.node_id} will send elections to {len(election_candidates)} node")
            # Check if there are no candidates, elect self as leader if no candidates
            if len(election_candidates) == 0:
                self.leader_id = self.node_id
                self.send_broadcast('COORDINATOR')
                # send broadcasts sends a message for each node in here
                self.increment_messages(len(self.nodes))
                return

            # If there are candidates call election on them
            ok_recieved = False
            for candidate in election_candidates:
                response = self.send_uni_cast(candidate, 'ELECTION')
                self.increment_messages()
                if (response is not None and response.status_code == 200):
                    ok_recieved = True
            # we should send all messages out before terminating
            if ok_recieved:
                return

            # If no 'ok' from higher candidate, you are then leader
            self.leader_id = self.node_id
            self.send_broadcast('COORDINATOR')
            # send broadcasts sends a message for each node in here
            self.increment_messages(len(self.nodes))

        finally:
            self.election_lock.release()

