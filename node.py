import socket
import time
import threading
import select
from collections import deque
from msg_class import Msg

NODE_PORT = 50000 # Port 50000 is broadcast and 50001 is node 1 etc...
TIME_DELAY = 5
TIMER_INTERVAL = 0.1
message_identifier = ['OK', 'COORDINATOR', 'BOOTUP', 'BOOTUP_RESPONSE', 'ELECTION', 'PING']

class Node(threading.Thread):
    """Node thread, listening when instantiated"""
    node_id: int
    is_alive: bool
    is_leader: bool
    leader_id: int
    nodes: list[int]
    has_received_ping_reply = tuple[bool, float]
    last_ok: float
    ongoing_election: bool
    election_time_check: float


    def __init__ (self, node_id: int, nodes: list[int]):
        super().__init__()
        self.node_id = node_id
        self.is_alive = True
        self.is_leader = False
        self.leader_id = -1
        self.nodes = nodes
        self.has_received_ping_reply = None
        self.ongoing_election = False

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
        self.nodes.append(node_id)
        
    def ping_leader(self):
        self.has_received_ping_reply = (True, time.time() + 3)
        self.send_uni_cast(self.leader_id, "PING", "request")


    def election(self, sender = None):

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
        # if (self.has_recieved_ok is False):
        #     self.broadcast_leader()
        return
    
    def check_for_ok(self):
        current_time = time.time()
        if current_time > self.has_recieved_ok[0][1]:
            rec_okay = self.has_recieved_ok.popleft()
            if not rec_okay[2]:
                self.broadcast_leader()

    def check_ping(self):
        current_time = time.time()
        if current_time > self.has_received_ping_reply[1]:
            if (not self.has_received_ping_reply[0]) and (not self.ongoing_election):
                self.election()
            self.has_received_ping_reply = None

            
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
        decoded = data.decode(), 
        messages = decoded.split('/')
        for msg in messages:
            src, dst, type, payload = msg.split("|", 3)
            src = int(src)
            print(f"src: {src}, dst: {dst}, type: {type}, payload: {payload}")

            # Check of the message was OK
            if type == "OK":
                self.has_recieved_ok = True

            # If it was a coordinantor message then update the leader I
            elif type == "COORDINATOR":
                self.leader_id = int(payload)

            elif type == "ELECTION":
                self.election(src)

            elif type == "PING":
                if (payload == "request" and self.is_alive):
                    # Im the leader and im alive
                    self.send_uni_cast(src, "PING", "reply")

                # Got a ping back from the leader
                elif (payload == "reply"):
                    self.has_received_ping_reply[0] = True

                

            elif type == "BOOTUP":
                src = int(src)
                self.new_node(src)
                
                if (self.is_alive):


            if not self.has_recieved_ok and time.time() > self.last_ok + TIME_DELAY:
                # current node is now leader
                self.broadcast_leader()


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
            if self.has_recieved_ok:
                self.check_queue()
                self.check_ping()

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


    def send_uni_cast(self, dst_node_id: int, msg_type: str, payload: str = ''):
        """Generic function for sending messages to one node

        Args:
            node_id (int): node's index
            msg (str): message to send
        """
        assert msg_type in message_identifier, 'message type should be in message_identifiers'
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(('localhost', int(NODE_PORT + dst_node_id)))
            message = Msg(self.node_id, dst_node_id, msg_type)
            s.sendall(message.format())
