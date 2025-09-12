from node import Node

class System:
    nodes: list[int]
    test_cases: list

    def __init__(self, amount_nodes: int, test_cases: list[str]):
        node_ids = list(range(0, amount_nodes))
        self.nodes = []
        for node_id in node_ids:
            node = Node(id, node_ids)
            node.start()
            self.nodes.append(node)
        test_cases = []
    
    def runs_test_cases(self, index: int) -> bool:
        pass
