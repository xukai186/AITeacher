import uuid


class MasteryService:
    @staticmethod
    def placement_levels(correct_by_node: dict[uuid.UUID, tuple[int, int]]) -> dict[str, int]:
        """
        P3 rule: level 3 if all correct for a node, else level 1.
        Returns JSON-serializable mapping {knowledge_node_id: level}.
        """
        out: dict[str, int] = {}
        for node_id, (correct, total) in correct_by_node.items():
            if total <= 0:
                continue
            out[str(node_id)] = 3 if correct == total else 1
        return out

