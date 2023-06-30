from typing import TYPE_CHECKING

from graphene import Boolean, InputField, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.manager import NodeManager
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import RelationshipCardinality
from infrahub.exceptions import NodeNotFound, ValidationError
from infrahub_client.utils import compare_lists

from ..types import RelatedNodeInput

if TYPE_CHECKING:
    from neo4j import AsyncSession


# pylint: disable=unused-argument,too-many-branches

RELATIONSHIP_PEERS_TO_IGNORE = ["Node"]


class RelationshipNodesInput(InputObjectType):
    id = InputField(String(required=True), description="ID of the node at the source of the relationship")
    name = InputField(String(required=True), description="Name of the relationship to add or remove nodes")
    nodes = InputField(
        List(of_type=RelatedNodeInput), description="List of nodes to add or remove to the relationships"
    )


class RelationshipMixin:
    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        if not (
            source := await NodeManager.get_one(
                session=session, id=data.get("id"), branch=branch, at=at, include_owner=True, include_source=True
            )
        ):
            raise NodeNotFound(branch, None, data.get("id"))

        # Check if the name of the relationship provided exist for this node and is of cardinality Many
        if data.get("name") not in source._schema.relationship_names:
            raise ValidationError(
                {"name": f"'{data.get('name')}' is not a valid relationship for '{source.get_kind()}'"}
            )

        rel_schema = source._schema.get_relationship(name=data.get("name"))
        if rel_schema.cardinality != RelationshipCardinality.MANY:
            raise ValidationError({"name": f"'{data.get('name')}' must be a relationship of cardinality Many"})

        # Query the node in the database and validate that all of them exist and are if the correct kind
        node_ids: List[str] = [node_data.get("id") for node_data in data.get("nodes")]
        nodes = await NodeManager.get_many(
            session=session, ids=node_ids, fields={"display_label": None}, branch=branch, at=at
        )

        _, _, in_list2 = compare_lists(list1=list(nodes.keys()), list2=node_ids)
        if in_list2:
            for node_id in in_list2:
                raise ValidationError(f"{node_id!r}: Unable to find the node in the database.")

        for node_id, node in nodes.items():
            if rel_schema.peer in RELATIONSHIP_PEERS_TO_IGNORE:
                continue
            if rel_schema.peer not in node.get_labels():
                raise ValidationError(f"{node_id!r} {node.get_kind()!r} is not a valid peer for '{rel_schema.peer}'")

        # The nodes that are already present in the db
        query = await RelationshipGetPeerQuery.init(
            session=session,
            source=source,
            at=at,
            rel=Relationship(schema=rel_schema, branch=branch, node=source),
        )
        await query.execute(session=session)
        existing_peers = {peer.peer_id: peer for peer in query.get_peers()}

        if cls.__name__ == "RelationshipAdd":
            for node_data in data.get("nodes"):
                if node_data.get("id") not in existing_peers.keys():
                    rel = Relationship(schema=rel_schema, branch=branch, at=at, node=source)
                    await rel.new(session=session, data=node_data)
                    await rel.save(session=session)

        elif cls.__name__ == "RelationshipRemove":
            for node_data in data.get("nodes"):
                if node_data.get("id") in existing_peers.keys():
                    rel = Relationship(schema=rel_schema, branch=branch, at=at, node=source)
                    await rel.load(session=session, data=existing_peers[node_data.get("id")])
                    await rel.delete(session=session)

        return cls(ok=True)


class RelationshipAdd(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()


class RelationshipRemove(RelationshipMixin, Mutation):
    class Arguments:
        data = RelationshipNodesInput(required=True)

    ok = Boolean()
