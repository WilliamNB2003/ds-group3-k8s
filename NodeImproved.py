"""
Improved bully election algorithm
"""
import time
from flask import jsonify
from nodeComposition import NodeComposition


class Node(NodeComposition):
    """Node thread, listening when instantiated"""

    def __init__ (self, node_id: int):
        super().__init__(node_id, True)

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
            self.messages_count += 1
            return jsonify({"status": "OK"}), 200

    # ---------------------------------------------------
    #  Methods called outside of node
    # ---------------------------------------------------
    def resetMessageCount(self):
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
        if response is None or not response.status_code == 200:
            if len(self.nodes) > 0:
                self.nodes.pop()
            self.election()
            # return
        # print('Leader is still alive: ', response.status_code)

    # ---------------------------------------------------
    # Methods called inside of node
    # ---------------------------------------------------
    def bootup(self):
        """
            Broadcasts to all other nodes that this node exists, so they update their table
        """
        print("discovery: node id: ", self.node_id)
        node_ids = self.discovery()
        node_ids_filtered = [nid for nid in node_ids if nid != self.node_id]
        self.nodes = self.nodes + node_ids_filtered
        # print("-------------- Node: ", self.node_id, " is trying to bootup... --------------")
        responses = self.send_broadcast('BOOTUP')
        print("responses from bootup: ", responses)
        # Update the leader ID for the booted up node
        if len(responses) == 0:
            self.election()

        for response in responses:
            if response.status_code == 404:
                continue

            data = response.json()
            if response and response.status_code == 200:
                self.leader_id = max(self.leader_id, int(data["leader_id"]))
                # break
        print(self.leader_id, self.node_id)
        if self.leader_id < self.node_id:
            self.election()

    def election(self):
        """
            Host an election, whenever a leader is either down or there is a new candidate
        """
        # Collect the ID's higher than my own:
        election_candidates = [node for node in self.nodes if (node > self.node_id)]
        # Check if there are no candidates, elect self as leader if no candidates
        if len(election_candidates) == 0:
            self.leader_id = self.node_id

        # If there are candidates call election on them
        highest_id = -1
        for candidate in election_candidates:
            response = self.send_uni_cast(candidate, 'ELECTION')
            self.messages_count += 1
            if (response is not None and response.status_code == 200):
                if highest_id < candidate:
                    highest_id = candidate
        
        if highest_id > self.node_id:
            # this candidate is now leader
            self.leader_id = highest_id
        else:
            # If no 'ok' from higher candidate, you are then leader
            self.leader_id = self.node_id

        # this node should always end up sending out who is coordinator
        self.send_broadcast('COORDINATOR')
