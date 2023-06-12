from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, Union

from infrahub.core import get_branch, registry
from infrahub.core.manager import NodeManager
from infrahub.core.query import Query

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch

# pylint: disable=redefined-builtin


class AccountTokenValidateQuery(Query):
    def __init__(self, token, *args, **kwargs):
        self.token = token
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        token_filter_perms, token_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(token_params)

        account_filter_perms, account_params = self.branch.get_query_filter_relationships(
            rel_labels=["r3", "r4", "r5", "r6", "r7", "r8"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(account_params)

        self.params["token_value"] = self.token

        query = """
        MATCH (at:AccountToken)-[r1:HAS_ATTRIBUTE]-(a:Attribute {name: "token"})-[r2:HAS_VALUE]-(av:AttributeValue { value: $token_value })
        WHERE %s
        WITH at
        MATCH (at)-[r3]-(:Relationship)-[r4]-(acc:Account)-[r5:HAS_ATTRIBUTE]-(an:Attribute {name: "name"})-[r6:HAS_VALUE]-(av:AttributeValue)
        MATCH (at)-[r3]-(:Relationship)-[r4]-(acc:Account)-[r7:HAS_ATTRIBUTE]-(ar:Attribute {name: "role"})-[r8:HAS_VALUE]-(avr:AttributeValue)
        WHERE %s
        """ % (
            "\n AND ".join(token_filter_perms),
            "\n AND ".join(account_filter_perms),
        )

        self.add_to_query(query)

        self.return_labels = ["at", "av", "avr", "acc"]

    def get_account_name(self):
        """Return the account name that matched the query or None."""
        if result := self.get_result():
            return result.get("av").get("value")

        return None

    def get_account_id(self) -> Optional[str]:
        """Return the account id that matched the query or a None."""
        if result := self.get_result():
            return result.get("acc").get("uuid")

        return None

    def get_account_role(self) -> str:
        """Return the account role that matched the query or a None."""
        if result := self.get_result():
            return result.get("avr").get("value")

        return "read-only"


async def validate_token(
    token, session: AsyncSession, branch: Union[Branch, str] = None, at=None
) -> Tuple[Optional[str], str]:
    branch = await get_branch(session=session, branch=branch)
    query = await AccountTokenValidateQuery.init(session=session, branch=branch, token=token, at=at)
    await query.execute(session=session)
    return query.get_account_id(), query.get_account_role()


async def get_account(
    account,
    session: AsyncSession,
    branch=None,
    at=None,
):
    # No default value supported for now
    if not account:
        return None

    if hasattr(account, "schema") and account.schema.kind == "Account":
        return account

    # Try to get it from the registry
    #   if not present in the registry, get it from the database directly
    #   and update the registry
    if account in registry.account:
        return registry.account[account]

    account_schema = registry.get_schema(name="Account")

    obj = await NodeManager.query(
        account_schema, filters={account_schema.default_filter: account}, branch=branch, at=at, session=session
    )
    registry.account[account] = obj

    return obj


def get_account_by_id(id: str):  # pylint: disable=unused-argument
    # No default value supported for now
    # if not id:
    return None

    # from .account import Account

    # if id in registry.account_id:
    #     return registry.account_id[id]

    # obj = Account.get(id=id)
    # if not obj:
    #     return None

    # registry.account[obj.name.value] = obj
    # registry.account_id[id] = obj
    # return obj
