import copy
import logging
import uuid
from asyncio import run as aiorun
from collections import defaultdict
from ipaddress import IPv4Network
from typing import Dict, List, Optional

import typer
from rich.logging import RichHandler

from infrahub_client import InfrahubClient, InfrahubNode, NodeNotFound


class NodeStore:
    """Temporary Store for InfrahubNode objects.

    Often while creating a lot of new objects,
    we need to save them in order to reuse them laterto associate them with another node for example.
    """

    def __init__(self):
        self._store = defaultdict(dict)

    def set(self, key: str, node: InfrahubNode) -> None:
        if not isinstance(node, InfrahubNode):
            raise TypeError(f"'node' must be of type InfrahubNode, not {type(InfrahubNode)!r}")

        node_kind = node._schema.kind
        self._store[node_kind][key] = node

    def get(self, key: str, kind: Optional[str] = None) -> InfrahubNode:

        if kind and kind not in self._store or key not in self._store[kind]:
            raise NodeNotFound(branch="n/a", node_type=kind, identifier=key, message="Unable to find the node in the Store")

        if kind:
            return self._store[kind][key]

        for kind in self._store.keys():
            if key in self._store[kind]:
                return self._store[kind][key]

        raise NodeNotFound(branch="n/a", node_type="n/a", identifier=key, message=f"Unable to find the node {key!r} in the Store")
