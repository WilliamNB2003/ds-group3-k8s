import sys
import time
import signal

from NodeImproved import Node
# from node import Node
class System:
    """
        System is a test class for the bully election (Non-improved)
    """
    nodes: list[Node]
    test_cases: list

    def __init__(self, amount_nodes: int):
        node_ids = list(range(1, amount_nodes + 1))
        self.nodes = []
        for node_id in node_ids:
            my_node = Node(node_id)
            my_node.start_node()
            self.nodes.append(my_node)
            # time.sleep(0.1)

    def kill_node(self, node_id: int):
        node_to_kill = self.nodes[node_id-1]
        node_to_kill.kill_node()
        print(f"killed node {node_id}!")
    
    def kill_leader(self):
        """Kills the first leader it comes across"""
        for idx, node in enumerate(self.nodes):
            if node.is_node_alive and node.leader_id == node.node_id:
                node.kill_node()
                print("killed node with id: ", node.node_id)
                return idx

    def revive_node(self, node_id: int):
        node_to_revive = self.nodes[node_id]
        node_to_revive.revive_node()
        print(f"reviveded node {node_id}!")
    
    def smallest_node(self):
        lowest = 65000
        index = -1
        for idx, node in enumerate(self.nodes):
            if node.node_id < lowest:
                lowest = node.node_id
                index = idx
        if index == -1:
            print('There was no nodes')

        # return 0 if there was no nodes, else return found index
        return_index = 0 if index == -1 else index
        return return_index
        
    def node_to_ping_leader(self, node_id: int):
        """
            Which node to ping the leader
        """
        pinging_node = self.nodes[node_id]
        pinging_node.ping_leader()
        
    def clearCount(self):
        for node in self.nodes:
            node.reset_message_count()

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
            count = node.messages_count
            print(f"node {node.node_id} message count: ", count)
            message_count += count
        
        return message_count

    def addNewNode(self):
        node_id = len(self.nodes) + 1
        my_node = Node(node_id)
        my_node.start_node()
        self.nodes.append(my_node)
        print(f"added node {node_id}")

    # Virker muligvis ikke, siden `node.is_alive` keeps being true
    def shutdown_all_nodes(self):
        """Properly shutdown all Flask servers and threads"""
        print(f"Shutting down {len(self.nodes)} nodes...")
        
        for node in self.nodes:
            try:
                if hasattr(node, 'shutdown'):
                    node.shutdown()
                    
            except Exception as e:
                print(f"Error shutting down node {node.node_id}: {e}")
        
        time.sleep(1)
        
        print("Waiting for threads to finish...")
        for node in self.nodes:
            if node.is_alive():
                print(f"Waiting for node {node.node_id} to shutdown...")
                node.join(timeout=3)
                if node.is_alive():
                    print(f"Node {node.node_id} thread did not shutdown gracefully, it may still be running")
        
        print("All nodes shutdown complete")
        sys.exit(0)


if __name__ == '__main__':
    messages_count = []
    system = System(amount_nodes=2)

    NR_OF_NODES = 5
    try:
        # time.sleep(0.4)
        for i in range(NR_OF_NODES):
            # kill leader and get messages from that
            system.clearCount()
            # kills the current leader
            leader_index = system.kill_leader()
            print("found leader index to be: ", leader_index)
            if not leader_index:
                # if no leader was found, wait for propegation
                time.sleep(2)
                leader_index = system.kill_leader()
                if not leader_index:
                    # if there still was no leader, then there is an issue
                    print(" !!!!---- THERE WAS NO LEADER")
                    sys.exit()
            # wait for leader to be down
            time.sleep(0.1)
            # should start an election
            system.node_to_ping_leader(system.smallest_node())
            time.sleep(3)
            print("\nafter killing leader")
            system.getSystemSummary()
            time.sleep(1)

            # now revive leader, and add new node
            system.revive_node(leader_index)
            system.addNewNode()
            # Allow time for all messages to be exchanged
            time.sleep(1)
            print("\n ---- after adding new node")
            messages_count.append(system.getSystemMessagesCount())
            system.getSystemSummary()
            print(messages_count)
            print('for loop done:', i)
            time.sleep(1)
        print('done :)')
        print(messages_count)
    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        print("cleaning up")
        system.shutdown_all_nodes()
