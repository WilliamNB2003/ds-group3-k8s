import socket
import time
import threading
import select
from collections import deque

NODE_PORT = 50000 # Port 50000 is broadcast and 50001 is node 1 etc...
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
    has_recieved_okay: deque[tuple[str, float, bool]] = deque()
    last_ok: float
    election_id_count: int


    def __init__ (self, node_id: int, nodes: list[int]):
        super().__init__()
        self.node_id = node_id
        self.is_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes
        self.election_id_count = 0

        # Broadcast
        self.bootup()
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
    
    def new_node(self, node_id):
        self.nodes[-1] = node_id
        

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

    def election(self, sender = None, election_id = None):
        election_id = self.election_id_count
        self.election_id_count += 1

        self.has_recieved_okay.append([election_id, time.time()+5, False])

        if (sender is not None):
            # send OK to sender of election
            self.send_uni_cast(sender, 'OK', self.node_id)

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
            self.send_uni_cast(candidate, 'ELECTION', self.node_id)

        # wait is done in listen_for_msg
        # time.sleep(3)

        # # If you have not received OK the broadcast that you are the leader
        # if (self.has_recieved_okay is False):
        #     self.broadcast_leader()
        return
    
    def check_queue(self):
        current_time = time.time()
        if current_time > self.has_recieved_okay[0][1]:
            rec_okay = self.has_recieved_okay.popleft()
            if not rec_okay[2]:
                self.broadcast_leader()

            
    # Listen for unicast messages
    def check_messages(self, server_socket):
        """"When a message has come """

        print(f"Node {self.node_id} listening...")
    
        # wait for a new client to connect
        client_conn, addr = server_socket.accept()
        # recv from this client
        data = client_conn.recv(512)

        # Close the connection to the client
        client_conn.close()

        # Decode the data
        decoded = data.decode(): int, 
        messages = decoded.split('/')
        for msg in messages:
            code, leader_id, sender_node_id = msg.split("|", 2)
            leader_id = int(leader_id)
            sender_node_id = int(sender_node_id)
            print(f"Message: {code}, Leader: {leader_id}, Sender: {sender_node_id}")

            # Check of the message was OK
            if code == "OK":
                self.has_recieved_okay = True

            # If it was a coordinantor message then update the leader I
            elif code == "COORDINATOR":
                self.leader_id = leader_id

            elif code == "ELECTION":
                self.election(sender_node_id)

            if not self.has_recieved_okay and time.time() > self.last_ok + TIME_DELAY:
                # current node is now leader
                self.broadcast_leader()

    # Listen for broadcast messages
    def handle_broadcast(self, socket):
        """"Handles broadcast messages like BOOTUP"""
        print("handle broadcast message")
        client_conn, addr = socket.accept()  
        # recv from this client
        data = client_conn.recv(512)

        # Close the connection to the client
        client_conn.close()

        # Decode the data
        decoded = data.decode()
        messages = decoded.split('/')
        for msg in messages:
            code, leader_id, sender_node_id = msg.split("|", 2)
            if code == "BOOTUP":
                leader_id = int(leader_id)
                sender_node_id = int(sender_node_id)
                self.new_node(sender_node_id)
            if code == "COORDINATOR":
                leader_id = int(leader_id)
                sender_node_id = int(sender_node_id)
                # new leader
                self.leader_id = sender_node_id
        print('handled broadcast messages')



    def run(self):
        """Main loop, keeps listening on port 50000 + node_id"""

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('localhost', NODE_PORT + self.node_id))
        server_socket.listen()

        broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        broadcast_socket.bind(('localhost', 50000))
        broadcast_socket.listen()
        server_to_listen = [server_socket, broadcast_socket]

        while True:
            if self.has_recieved_okay:
                self.check_queue()

            ready, _, _ = select.select(server_to_listen, [], [], TIMER_INTERVAL)
                
            if ready:
                for sock in server_to_listen:
                    client_conn, addr = sock.accept()
                    if sock == server_socket:
                        self.check_queue(server_socket)
                    else:
                        # broadcast message
                        self.handle_broadcast(sock)
            else:
                # now check for timers expired
                pass

    def broadcast_leader(self):
        self.send_broadcast('COORDINATOR')
        print(f"node {self.node_id} is now leader")


    def send_broadcast(self, msg: str, sender_node_id, leader = -1):
        assert msg in message_identifier, "message type should be in message_identifier"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', int(NODE_PORT)))
            payload = f"/{msg}|{leader}|{sender_node_id}".encode()
            s.sendall(payload)
            # data_rec = s.recv(512) # Line to recieve data


    def send_uni_cast(self, node_id: int, msg: str, sender_node_id, leader = None):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        assert msg in message_identifier, 'message type should be in message_identifiers'
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', int(NODE_PORT + node_id)))
            payload = f"/{msg}|{leader}|{sender_node_id}".encode()
            s.sendall(payload)
            # data_rec = s.recv(512) # Line to recieve data
