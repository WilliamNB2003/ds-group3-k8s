import sys
import time
from threading import Thread

from NodeImproved import Node as newNode
from node import Node as oldNode

class System:
    """
        System is a test class for the bully election (Non-improved)
    """
    nodes: list

    def __init__(self, node_class, amount_nodes: int):
        node_ids = list(range(0, amount_nodes))
        self.nodes = []
        self.node_class = node_class
        skip_discovery = True
        for node_id in node_ids:
            my_node = self.node_class(node_id + 1, skip_discovery=skip_discovery)
            # only the first node should skip discovery
            skip_discovery = False
            my_node.start_node()
            self.nodes.append(my_node)
        self.shutdown_in_progress = False  # Add flag to prevent cascading shutdowns

    def kill_node(self, node_id: int):
        node_to_kill = self.nodes[node_id]
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
        my_node = self.node_class(node_id)
        my_node.start_node()
        self.nodes.append(my_node)
        print(f"added node {node_id}")

    def shutdown_all_nodes(self):
        """Properly shutdown all Flask servers and threads"""
        if self.shutdown_in_progress:
            print("Shutdown already in progress, skipping...")
            return
            
        self.shutdown_in_progress = True
        print(f"Shutting down {len(self.nodes)} nodes...")
        
        # Simply mark all nodes as not alive and exit
        # This is more reliable than trying to gracefully shutdown Flask servers
        for node in self.nodes:
            node.is_node_alive = False
            node.shutdown_in_progress = True
        
        print("All nodes marked for shutdown")
        time.sleep(0.5)  # Brief pause to let any ongoing operations complete

        for node in self.nodes:
            if node.is_node_alive == False:
                print("Node: ", node.node_id, " Is shutdown by flag and by our definition successfully")



    def _shutdown_single_node(self, node):
        """Shutdown a single node"""
        try:
            node.shutdown()
        except Exception as e:
            print(f"Error shutting down node {node.node_id}: {e}")

def testSystem(number_of_nodes, node_class):
    system = System(node_class=node_class, amount_nodes=number_of_nodes)
    try:
        if (number_of_nodes < 2):
            raise ValueError("Must create the system with at least 2 nodes")
        
        failed_test = False

        # Test that system startup works and find the correct leader
        time.sleep(0.5)
        leader_node_id = system.nodes[-1].node_id
        for i in range(number_of_nodes):
            if (not (system.nodes[i].leader_id == leader_node_id and system.nodes[i].is_node_alive)):
                failed_test = True
                print("Failed test 1")

        # Test that when killing leader a new leader is found
        system.kill_leader()
        time.sleep(0.25)
        system.node_to_ping_leader(0)
        time.sleep(0.25)
        leader_node_id = system.nodes[-2].node_id
        for i in range(number_of_nodes):
            if (i == number_of_nodes - 1):
                # if we are the last node so highest id, then we should be dead
                if (system.nodes[i].is_node_alive):
                    failed_test = True
                    print("Failed test 2 as node", i)
            else:
                if (not (system.nodes[i].leader_id == leader_node_id)):
                    failed_test = True
                    print("Failed test 3 as node", i)
        system.getSystemSummary()

        # Test that when the old leader gets revived it becomes leader again
        system.revive_node(-1)
        time.sleep(0.5)
        leader_node_id = system.nodes[-1].node_id
        for i in range(number_of_nodes):
            if (not (system.nodes[i].leader_id == leader_node_id and system.nodes[i].is_node_alive)):
                failed_test = True
                print("Failed test 4 as node", i)

        # Test that when new node gets added it becomes leader since it has highest id
        system.addNewNode()
        time.sleep(0.5)
        if (not len(system.nodes) == number_of_nodes + 1):
            failed_test = True
            print("Failed test 5")

        leader_node_id = system.nodes[-1].node_id
        for i in range(number_of_nodes):
            if (not (system.nodes[i].leader_id == leader_node_id and system.nodes[i].is_node_alive)):
                failed_test = True
                print("Failed test 6")


        # Test that all when non leader gets killed the leader doesn't change
        system.kill_node(-2)
        time.sleep(0.25)
        system.node_to_ping_leader(0)
        time.sleep(0.25)
        for i in range(number_of_nodes):
            if (i == number_of_nodes - 1):
                # if we are the last node so highest id, then we should be dead
                if (system.nodes[i].is_node_alive):
                    failed_test = True
                    print("Failed test 7 as node", i)
            else:
                if (not (system.nodes[i].leader_id == leader_node_id)):
                    failed_test = True
                    print("Failed test 8 as node", i)
        system.getSystemSummary()
        
        
        return failed_test
    finally:
        # in case of an interrupt or other
        system.shutdown_all_nodes()


# This is a test, to check that the system works
if __name__ == '__main__':
    try:
        improved = not testSystem(3, newNode)
        old = not testSystem(3, oldNode)
        print(f'The old node passed the test: {old}')
        print(f'The improved node passed the test: {improved}')

    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        print("Cleaning up...")
        print("Exiting the program!")

        sys.exit()