from node import Node
import time

class System:
    """
        System is a test class for the bully election (Non-improved)
    """
    nodes: list[Node]
    test_cases: list

    def __init__(self, amount_nodes: int):
        node_ids = list(range(1, amount_nodes + 1))
        self.nodes = []
        known_nodes = []
        for node_id in node_ids:
            my_node = Node(node_id, known_nodes)
            my_node.start_node()
            self.nodes.append(my_node)
            known_nodes.append(node_id)
            
    def kill_node(self, node_id: int):
        node_to_kill = self.nodes[node_id-1]
        node_to_kill.kill_node()
        print(f"killed node {node_id}!")

    def revive_node(self, node_id: int):
        node_to_kill = self.nodes[node_id-1]
        node_to_kill.kill_node()
        print(f"killed node {node_id}!")

    def node_to_ping_leader(self, node_id: int):
        """
            Which node to ping the leader
        """
        pinging_node = self.nodes[node_id-1]
        pinging_node.ping_leader()

    def getSystemSummary(self):
        print("\n----------System symmary----------")
        for node in self.nodes:
            if node.is_node_alive:
                state = "alive."
            else:
                state = "dead. "
            print(f"{node.node_id}: {state} Believed leader: {node.leader_id}")
        print("----------------------------------")


if __name__ == '__main__':
    system = System(20)
    print('made nodes :)')
    # while True:
    system.getSystemSummary()
    time.sleep(10)
    system.kill_node(20)
    system.kill_node(19)
    system.kill_node(18)
    system.kill_node(16)
    system.kill_node(11)
    system.revive_node(20)
    time.sleep(1)
    system.node_to_ping_leader(8)
    system.getSystemSummary()
    
    # Add new node
     my_node = Node(node_id, known_nodes)
    my_node.start_node()
    self.nodes.append(my_node)
    known_nodes.append(node_id)

    