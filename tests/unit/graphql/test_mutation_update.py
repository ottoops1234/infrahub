import graphene
import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_update_simple_object(default_branch, car_person_schema):

    obj = Node("Person").new(name="John", height=180).save()

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors == None
    assert result.data["person_update"]["ok"] == True

    obj1 = NodeManager.get_one(obj.id)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


@pytest.mark.asyncio
async def test_update_invalid_object(default_branch, car_person_schema):

    query = """
    mutation {
        person_update(data: {id: "XXXXXX", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """

    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "Unable to find the node in the database." in result.errors[0].message


@pytest.mark.asyncio
async def test_update_invalid_input(default_branch, car_person_schema):

    obj = Node("Person").new(name="John", height=180).save()

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: False }}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


@pytest.mark.asyncio
async def test_update_relationship_many(default_branch, person_tag_schema):

    t1 = Node("Tag").new(name="Blue", description="The Blue tag").save()
    t2 = Node("Tag").new(name="Red").save()
    p1 = Node("Person").new(firstname="John", lastname="Doe").save()

    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ "%s" ] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
    )
    result = await graphql(
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors == None
    assert result.data["person_update"]["ok"] == True
    assert len(result.data["person_update"]["object"]["tags"]) == 1
