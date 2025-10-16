import sys
import time
import signal

# from NodeImproved import Node
from node import Node
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
            count = node.getMessageCount()
            print(f"node {node.node_id} message count: ", count)
            message_count += count
        
        return message_count

    def addNewNode(self):
        node_id = len(self.nodes) + 1
        my_node = Node(node_id)
        my_node.start_node()
        self.nodes.append(my_node)
        print(f"added node {node_id}")

    def shutdown_all_nodes(self):
        """Properly shutdown all Flask servers and threads"""
        print(f"Shutting down {len(self.nodes)} nodes...")
        
        for node in self.nodes:
            try:
                if hasattr(node, 'shutdown'):
                    node.shutdown()
                    
            except Exception as e:
                print(f"Error shutting down node {node.node_id}: {e}")
        
        # Give a moment for shutdown to propagate
        time.sleep(1)
        
        # Wait for threads to finish (with timeout)
        print("Waiting for threads to finish...")
        for node in self.nodes:
            while node.is_alive():
                print(f"Waiting for node {node.node_id} to shutdown...")
                node.join(timeout=3)
                if node.is_alive():
                    print(f"Node {node.node_id} thread did not shutdown gracefully, it may still be running")
        
        print("All nodes shutdown complete")


if __name__ == '__main__':
    messages_count = []
    system = System(amount_nodes=2)
    def signal_handler(sig, frame):
        print('\nShutting down gracefully...')
        system.shutdown_all_nodes()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        # time.sleep(0.4)
        for i in range(50):
            system.clearCount()
            system.kill_node(i+2)
            system.node_to_ping_leader(1)
            # time.sleep(1)
            messages_count.append(system.getSystemMessagesCount())
            system.getSystemSummary()
            system.revive_node(i+2)
            system.addNewNode()
            time.sleep(0.5)
            print('for loop done:', i)
        print('done :)')
        print(messages_count)
    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        print("cleaning up")
        system.shutdown_all_nodes()
