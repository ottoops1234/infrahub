import pytest

from neo4j import AsyncSession

from infrahub.core.query import Query


class Query01(Query):
    async def query_init(self, session: AsyncSession, *args, **kwargs):
        query = """
        MATCH (n) WHERE n.uuid = $uuid
        MATCH (n)-[r1]-(at:Attribute)-[r2]-(av)
        """

        self.return_labels = ["n", "at", "av", "r1", "r2"]
        self.params["uuid"] = "5ffa45d4"

        self.add_to_query(query)


async def test_query_base(session):

    query = await Query01.init(session=session)
    expected_query = "MATCH (n) WHERE n.uuid = $uuid\nMATCH (n)-[r1]-(at:Attribute)-[r2]-(av)\nRETURN n,at,av,r1,r2"

    assert query.get_query() == expected_query


async def test_query_results(session, simple_dataset_01):

    query = await Query01.init(session=session)

    assert query.has_been_executed is False
    await query.execute(session=session)

    assert query.has_been_executed is True

    assert query.num_of_results == 3
    assert query.results[0].get("at") is not None


async def test_query_async(session, simple_dataset_01):

    query = await Query01.init(session=session)

    assert query.has_been_executed is False
    await query.execute(session=session)

    assert query.has_been_executed is True

    assert query.num_of_results == 3
    assert query.results[0].get("at") is not None
