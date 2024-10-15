from typing import Generic, TypeVar

from pydantic import BaseModel


class NodeSocket(BaseModel):
    id: int
    name: str


class GraphNode(BaseModel):
    id: int
    inputs: list[NodeSocket]
    outputs: list[NodeSocket]


class GraphEdge(BaseModel):
    id: int

    from_node_id: int
    from_socket_id: int

    to_node_id: int
    to_socket_id: int


GraphNodeType = TypeVar("GraphNodeType", bound=GraphNode)


class Graph(BaseModel, Generic[GraphNodeType]):
    nodes: list[GraphNodeType]
    edges: list[GraphEdge]
