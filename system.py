from NodeImproved import Node
# from node import Node

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
        node_to_revive = self.nodes[node_id-1]
        node_to_revive.revive_node()
        print(f"reviveded node {node_id}!")

    def node_to_ping_leader(self, node_id: int):
        """
            Which node to ping the leader
        """
        pinging_node = self.nodes[node_id-1]
        pinging_node.ping_leader()
        
    def clearCount(self):
        for node in self.nodes:
            node.resetMessageCount()

    def getSystemSummary(self):
        print("\n---------- System summary ----------")
        for node in self.nodes:
            if node.is_node_alive:
                state = "alive."
            else:
                state = "dead. "
            print(f"{node.node_id}: {state} Believed leader: {node.leader_id}")
        
        print(f"Total Message Count: {self.getSystemMessagesCount()}")
        print("----------------------------------")

    def getSystemMessagesCount(self):
        message_count = 0
        for node in self.nodes:
            print(node.messages_count)
            message_count += node.messages_count
        
        return message_count

    def addNewNode(self):
        node_id = len(self.nodes) + 1
        my_node = Node(node_id, list(range(1, node_id)))
        my_node.start_node()
        self.nodes.append(my_node)
        print(f"added node {node_id}")


if __name__ == '__main__':
    message_count = []
    system = System(2)
    time.sleep(0.4)
    for i in range(8):
        system.clearCount()
        system.kill_node(i+2)
        system.node_to_ping_leader(1)
        time.sleep(0.3)
        message_count.append(system.getSystemMessagesCount())
        # system.getSystemSummary()
        system.revive_node(i+2)
        system.addNewNode()
        time.sleep(0.3)
    print(message_count)








    # # while True:
    # system.getSystemSummary()
    # time.sleep(7)
    # system.kill_node(17)
    # system.kill_node(18)
    # system.kill_node(16)
    # system.kill_node(11)
    # time.sleep(1)
    # system.node_to_ping_leader(8)
    # system.getSystemSummary()
    # system.revive_node(18)
    # system.getSystemSummary()
    # system.revive_node(16)
    # system.getSystemSummary()

    # # Add new node
    # time.sleep(1)
    # system.addNewNode()
    # system.getSystemSummary()

