import socket
import time
import threading
import select
from queue import Queue

NODE_PORT = 50000
TIME_DELAY = 5
TIMER_INTERVAL = 0.1
message_identifier = ['OK', 'COORDINATOR', 'BOOTUP', 'ELECTION']

class Node(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_alive: bool
    is_leader: bool
    leader_id: int
    nodes: list[int]
    has_recieved_okay: Queue[tuple[str, float, bool]]
    last_ok: float


    def __init__ (self, node_id: int, nodes: list[int]):
        super().__init__()
        self.node_id = node_id
        self.is_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes

        # main loop
        self.run()

    def bootup(self):
        """
            Broadcasts to all other nodes that this node exists, so they update their table
        """
        self.send_broadcast('BOOTUP')
        print(f'node {self.node_id} booted up..')

    def kill_node(self):
        self.is_alive = False

    def revive_node(self):
        self.is_alive = True

    def ping_leader(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # timeout is 3 seconds
                s.settimeout(3)
                # Try to ping the leader
                s.connect(("localhost", NODE_PORT + self.leader_id)) 
                return True

         # Cannot reach the leader
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            print(f'error: {e}')
            return False

    def election(self, sender = None):
        self.has_recieved_okay = False
        self.last_ok = time.time()

        if (sender is not None):
            # send OK to sender of election
            self.send_uni_cast(sender, 'OK')

        # Collect the ID's higher than my own:
        election_candidates = []
        for node in self.nodes:
            if (node > self.node_id):
                election_candidates.append(node)
        
        # Check if there are no candidates
        if (len(election_candidates) == 0):
            self.broadcast_leader()
            return

        # If there are candidates call election on them
        for candidate in election_candidates:
            self.send_uni_cast(candidate, 'ELECTION')

        # wait is done in listen_for_msg
        # time.sleep(3)

        # # If you have not received OK the broadcast that you are the leader
        # if (self.has_recieved_okay is False):
        #     self.broadcast_leader()
        return
    
    def check_queue(self):
        current_time = time.time()

    def check_messages(self, server_socket):

        print(f"Node {self.node_id} listening...")
    
        # wait for a new client to connect
        client_conn, addr = server_socket.accept()  
        # recv from this client
        data = client_conn.recv(512)

        # Close the connection to the client
        client_conn.close()

        # Decode the data
        decoded = data.decode()
        msg, leader_id = decoded.split("|", 1)
        leader_id = int(leader_id)
        print(f"Message: {msg}, Leader: {leader_id}")

        # Check of the message was OK
        if msg == "OK":
            self.has_recieved_okay = True

        # If it was a coordinantor message then update the leader I
        elif msg == "COORDINATOR":
            self.leader_id = leader_id

        elif msg == "ELECTION":
            

        if not self.has_recieved_okay and time.time() > self.last_ok + TIME_DELAY:
            # current node is now leader
            self.broadcast_leader()
        

    def run(self):
        """Main class loop, keeps listening on port 50000 + node_id"""

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('localhost', NODE_PORT + self.node_id))
        server_socket.listen()

        while True:
            if self.has_recieved_okay.empty():
            ready, _, _ = select.select([server_socket], [], [], TIMER_INTERVAL)
                
            if ready:
                self.check_queue(server_socket)
            else:
                # now check for timers expired
                pass

    def broadcast_leader(self):
        self.send_broadcast('COORDINATOR')
        print(f"node {self.node_id} is now leader")


    def send_broadcast(self, msg: str):
        assert msg in message_identifier, "message type should be in message_identifier"
        for node in self.nodes:
            self.send_uni_cast(node, msg)


    def send_uni_cast(self, node_id: int, msg: str, leader = None):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        assert msg in message_identifier, 'message type should be in message_identifiers'
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', int(NODE_PORT + node_id)))
            payload = f"{msg}|{leader}".encode()
            s.sendall(payload)
            # data_rec = s.recv(512) # Line to recieve data
