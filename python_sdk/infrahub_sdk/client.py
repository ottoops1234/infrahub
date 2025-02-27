from __future__ import annotations

import asyncio
import copy
import logging
from functools import wraps
from time import sleep
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, MutableMapping, Optional, Type, TypedDict, Union

import httpx
import ujson
from typing_extensions import NotRequired, Self
from typing_extensions import TypedDict as ExtensionTypedDict

from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.branch import (
    BranchData,
    InfrahubBranchManager,
    InfrahubBranchManagerSync,
)
from infrahub_sdk.config import Config
from infrahub_sdk.constants import InfrahubClientMode
from infrahub_sdk.data import RepositoryData
from infrahub_sdk.exceptions import (
    AuthenticationError,
    Error,
    GraphQLError,
    NodeNotFoundError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.graphql import Query
from infrahub_sdk.node import (
    InfrahubNode,
    InfrahubNodeSync,
)
from infrahub_sdk.object_store import ObjectStore, ObjectStoreSync
from infrahub_sdk.queries import get_commit_update_mutation
from infrahub_sdk.query_groups import InfrahubGroupContext, InfrahubGroupContextSync
from infrahub_sdk.schema import InfrahubSchema, InfrahubSchemaSync, NodeSchema
from infrahub_sdk.store import NodeStore, NodeStoreSync
from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.types import AsyncRequester, HTTPMethod, SyncRequester
from infrahub_sdk.utils import decode_json, is_valid_uuid

if TYPE_CHECKING:
    from types import TracebackType

# pylint: disable=redefined-builtin  disable=too-many-lines


class NodeDiff(ExtensionTypedDict):
    branch: str
    kind: str
    id: str
    action: str
    display_label: str
    elements: List[NodeDiffElement]


class NodeDiffElement(ExtensionTypedDict):
    name: str
    element_type: str
    action: str
    summary: NodeDiffSummary
    peers: NotRequired[List[NodeDiffPeer]]


class NodeDiffSummary(ExtensionTypedDict):
    added: int
    updated: int
    removed: int


class NodeDiffPeer(ExtensionTypedDict):
    action: str
    summary: NodeDiffSummary


class ProcessRelationsNode(TypedDict):
    nodes: List[InfrahubNode]
    related_nodes: List[InfrahubNode]


class ProcessRelationsNodeSync(TypedDict):
    nodes: List[InfrahubNodeSync]
    related_nodes: List[InfrahubNodeSync]


def handle_relogin(func: Callable[..., Coroutine[Any, Any, httpx.Response]]):  # type: ignore[no-untyped-def]
    @wraps(func)
    async def wrapper(client: InfrahubClient, *args: Any, **kwargs: Any) -> httpx.Response:
        response = await func(client, *args, **kwargs)
        if response.status_code == 401:
            errors = response.json().get("errors", [])
            if "Expired Signature" in [error.get("message") for error in errors]:
                await client.login(refresh=True)
                return await func(client, *args, **kwargs)
        return response

    return wrapper


def handle_relogin_sync(func: Callable[..., httpx.Response]):  # type: ignore[no-untyped-def]
    @wraps(func)
    def wrapper(client: InfrahubClientSync, *args: Any, **kwargs: Any) -> httpx.Response:
        response = func(client, *args, **kwargs)
        if response.status_code == 401:
            errors = response.json().get("errors", [])
            if "Expired Signature" in [error.get("message") for error in errors]:
                client.login(refresh=True)
                return func(client, *args, **kwargs)
        return response

    return wrapper


class BaseClient:
    """Base class for InfrahubClient and InfrahubClientSync"""

    def __init__(
        self,
        address: str = "",
        config: Optional[Union[Config, Dict[str, Any]]] = None,
    ):
        self.client = None
        self.headers = {"content-type": "application/json"}
        self.access_token: str = ""
        self.refresh_token: str = ""
        if isinstance(config, Config):
            self.config = config
        else:
            config = config or {}
            self.config = Config(**config)

        self.default_branch = self.config.default_infrahub_branch
        self.default_timeout = self.config.timeout
        self.config.address = address or self.config.address
        self.insert_tracker = self.config.insert_tracker
        self.log = self.config.logger or logging.getLogger("infrahub_sdk")
        self.address = self.config.address
        self.mode = self.config.mode
        self.pagination_size = self.config.pagination_size
        self.retry_delay = self.config.retry_delay
        self.retry_on_failure = self.config.retry_on_failure

        if self.config.api_token:
            self.headers["X-INFRAHUB-KEY"] = self.config.api_token

        self.max_concurrent_execution = self.config.max_concurrent_execution

        self.update_group_context = self.config.update_group_context
        self.identifier = self.config.identifier
        self.group_context: Union[InfrahubGroupContext, InfrahubGroupContextSync]
        self._initialize()

    def _initialize(self) -> None:
        """Sets the properties for each version of the client"""

    def _record(self, response: httpx.Response) -> None:
        self.config.custom_recorder.record(response)

    def _echo(self, url: str, query: str, variables: Optional[dict] = None) -> None:
        if self.config.echo_graphql_queries:
            print(f"URL: {url}")
            print(f"QUERY:\n{query}")
            if variables:
                print(f"VARIABLES:\n{ujson.dumps(variables, indent=4)}\n")

    def start_tracking(
        self,
        identifier: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        delete_unused_nodes: bool = False,
        group_type: Optional[str] = None,
    ) -> Self:
        self.mode = InfrahubClientMode.TRACKING
        identifier = identifier or self.identifier or "python-sdk"
        self.set_context_properties(
            identifier=identifier, params=params, delete_unused_nodes=delete_unused_nodes, group_type=group_type
        )
        return self

    def set_context_properties(
        self,
        identifier: str,
        params: Optional[Dict[str, str]] = None,
        delete_unused_nodes: bool = True,
        reset: bool = True,
        group_type: Optional[str] = None,
    ) -> None:
        if reset:
            if isinstance(self, InfrahubClient):
                self.group_context = InfrahubGroupContext(self)
            elif isinstance(self, InfrahubClientSync):
                self.group_context = InfrahubGroupContextSync(self)
        self.group_context.set_properties(
            identifier=identifier, params=params, delete_unused_nodes=delete_unused_nodes, group_type=group_type
        )

    def _graphql_url(
        self,
        branch_name: Optional[str] = None,
        at: Optional[Union[str, Timestamp]] = None,
    ) -> str:
        url = f"{self.config.address}/graphql"
        if branch_name:
            url += f"/{branch_name}"

        url_params = {}
        if at:
            at = Timestamp(at)
            url_params["at"] = at.to_string()
            url += "?" + "&".join([f"{key}={value}" for key, value in url_params.items()])

        return url

    def _build_ip_address_allocation_query(
        self, resource_pool_id: str, identifier: Optional[str] = None, data: Optional[Dict[str, Any]] = None
    ) -> str:
        mutation_definition = "mutation AllocateIPAddress"
        mutation_parameters = f'id: "{resource_pool_id}"'
        if identifier:
            mutation_parameters += f', identifier: "{identifier}"'
        if data:
            mutation_definition += "($data: GenericScalar)"
            mutation_parameters += ", data: $data"

        return """
            %s {
                IPAddressPoolGetResource(data: {
                    %s
                }) {
                    ok
                    node {
                        id
                        kind
                        identifier
                        display_label
                    }
                }
            }
        """ % (mutation_definition, mutation_parameters)

    def _build_ip_prefix_allocation_query(
        self,
        resource_pool_id: str,
        identifier: Optional[str] = None,
        prefix_length: Optional[int] = None,
        member_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        mutation_definition = "mutation AllocateIPPrefix"
        mutation_parameters = f'id: "{resource_pool_id}"'
        if identifier:
            mutation_parameters += f', identifier: "{identifier}"'
        if prefix_length:
            mutation_parameters += f", prefix_length: {prefix_length}"
        if member_type:
            mutation_parameters += f', member_type: "{member_type}"'
        if data:
            mutation_definition += "($data: GenericScalar)"
            mutation_parameters += ", data: $data"

        return """
            %s {
                IPPrefixPoolGetResource(data: {
                    %s
                }) {
                    ok
                    node {
                        id
                        kind
                        identifier
                        display_label
                    }
                }
            }
        """ % (mutation_definition, mutation_parameters)


class InfrahubClient(BaseClient):
    """GraphQL Client to interact with Infrahub."""

    group_context: InfrahubGroupContext

    def _initialize(self) -> None:
        self.schema = InfrahubSchema(self)
        self.branch = InfrahubBranchManager(self)
        self.object_store = ObjectStore(self)
        self.store = NodeStore()
        self.concurrent_execution_limit = asyncio.Semaphore(self.max_concurrent_execution)
        self._request_method: AsyncRequester = self.config.requester or self._default_request_method
        self.group_context = InfrahubGroupContext(self)

    @classmethod
    async def init(
        cls,
        address: str = "",
        config: Optional[Union[Config, Dict[str, Any]]] = None,
    ) -> InfrahubClient:
        return cls(address=address, config=config)

    async def create(
        self,
        kind: str,
        data: Optional[dict] = None,
        branch: Optional[str] = None,
        **kwargs: Any,
    ) -> InfrahubNode:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        if not data and not kwargs:
            raise ValueError("Either data or a list of keywords but be provided")

        return InfrahubNode(client=self, schema=schema, branch=branch, data=data or kwargs)

    async def delete(self, kind: str, id: str, branch: Optional[str] = None) -> None:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        node = InfrahubNode(client=self, schema=schema, branch=branch, data={"id": id})
        await node.delete()

    async def get(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        populate_store: bool = False,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> InfrahubNode:
        branch = branch or self.default_branch
        schema = await self.schema.get(kind=kind, branch=branch)

        filters: MutableMapping[str, Any] = {}

        if id:
            if not is_valid_uuid(id) and isinstance(schema, NodeSchema) and schema.default_filter:
                filters[schema.default_filter] = id
            else:
                filters["ids"] = [id]
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        results = await self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
            **filters,
        )  # type: ignore[arg-type]

        if len(results) == 0:
            raise NodeNotFoundError(branch_name=branch, node_type=kind, identifier=filters)
        if len(results) > 1:
            raise IndexError("More than 1 node returned")

        return results[0]

    async def _process_nodes_and_relationships(
        self, response: Dict[str, Any], schema_kind: str, branch: str, prefetch_relationships: bool
    ) -> ProcessRelationsNode:
        """Processes InfrahubNode and their Relationships from the GraphQL query response.

        Args:
            response (Dict[str, Any]): The response from the GraphQL query.
            schema_kind (str): The kind of schema being queried.
            branch (str): The branch name.
            prefetch_relationships (bool): Flag to indicate whether to prefetch relationship data.

        Returns:
            ProcessRelationsNodeSync: A TypedDict containing two lists:
                - 'nodes': A list of InfrahubNode objects representing the nodes processed.
                - 'related_nodes': A list of InfrahubNode objects representing the related nodes
        """

        nodes: List[InfrahubNode] = []
        related_nodes: List[InfrahubNode] = []

        for item in response.get(schema_kind, {}).get("edges", []):
            node = await InfrahubNode.from_graphql(client=self, branch=branch, data=item)
            nodes.append(node)

            if prefetch_relationships:
                await node._process_relationships(node_data=item, branch=branch, related_nodes=related_nodes)

        return ProcessRelationsNode(nodes=nodes, related_nodes=related_nodes)

    async def all(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
    ) -> List[InfrahubNode]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.

        Returns:
            List[InfrahubNode]: List of Nodes
        """
        return await self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
        )

    async def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        partial_match: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNode]:
        """Retrieve nodes of a given kind based on provided filters.

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.
            partial_match (bool, optional): Allow partial match of filter criteria for the query.
            **kwargs (Any): Additional filter criteria for the query.

        Returns:
            List[InfrahubNodeSync]: List of Nodes that match the given filters.
        """
        schema = await self.schema.get(kind=kind)

        branch = branch or self.default_branch
        if at:
            at = Timestamp(at)

        node = InfrahubNode(client=self, schema=schema, branch=branch)
        filters = kwargs

        if filters:
            node.validate_filters(filters=filters)

        nodes: List[InfrahubNode] = []
        related_nodes: List[InfrahubNode] = []

        has_remaining_items = True
        page_number = 1

        while has_remaining_items:
            page_offset = (page_number - 1) * self.pagination_size

            query_data = await InfrahubNode(client=self, schema=schema, branch=branch).generate_query_data(
                offset=offset or page_offset,
                limit=limit or self.pagination_size,
                filters=filters,
                include=include,
                exclude=exclude,
                fragment=fragment,
                prefetch_relationships=prefetch_relationships,
                partial_match=partial_match,
            )
            query = Query(query=query_data)
            response = await self.execute_graphql(
                query=query.render(),
                branch_name=branch,
                at=at,
                tracker=f"query-{str(schema.kind).lower()}-page{page_number}",
            )

            process_result: ProcessRelationsNode = await self._process_nodes_and_relationships(
                response=response, schema_kind=schema.kind, branch=branch, prefetch_relationships=prefetch_relationships
            )
            nodes.extend(process_result["nodes"])
            related_nodes.extend(process_result["related_nodes"])

            remaining_items = response[schema.kind].get("count", 0) - (page_offset + self.pagination_size)
            if remaining_items < 0 or offset is not None or limit is not None:
                has_remaining_items = False

            page_number += 1

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
            related_nodes = list(set(related_nodes))
            for node in related_nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)

        return nodes

    def clone(self) -> InfrahubClient:
        """Return a cloned version of the client using the same configuration"""
        return InfrahubClient(config=self.config)

    async def execute_graphql(
        self,
        query: str,
        variables: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[Union[str, Timestamp]] = None,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
        tracker: Optional[str] = None,
    ) -> Dict:
        """Execute a GraphQL query (or mutation).
        If retry_on_failure is True, the query will retry until the server becomes reacheable.

        Args:
            query (_type_): GraphQL Query to execute, can be a query or a mutation
            variables (dict, optional): Variables to pass along with the GraphQL query. Defaults to None.
            branch_name (str, optional): Name of the branch on which the query will be executed. Defaults to None.
            at (str, optional): Time when the query should be executed. Defaults to None.
            timeout (int, optional): Timeout in second for the query. Defaults to None.
            raise_for_error (bool, optional): Flag to indicate that we need to raise an exception if the response has some errors. Defaults to True.
        Raises:
            GraphQLError: _description_

        Returns:
            _type_: _description_
        """

        url = self._graphql_url(branch_name=branch_name, at=at)

        payload: Dict[str, Union[str, dict]] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = copy.copy(self.headers or {})
        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        self._echo(url=url, query=query, variables=variables)

        retry = True
        resp = None
        while retry:
            retry = self.retry_on_failure
            try:
                resp = await self._post(url=url, payload=payload, headers=headers, timeout=timeout)

                if raise_for_error:
                    resp.raise_for_status()

                retry = False
            except ServerNotReachableError:
                if retry:
                    self.log.warning(
                        f"Unable to connect to {self.address}, will retry in {self.retry_delay} seconds .."
                    )
                    await asyncio.sleep(delay=self.retry_delay)
                else:
                    self.log.error(f"Unable to connect to {self.address} .. ")
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in [401, 403]:
                    response = decode_json(response=exc.response, url=url)
                    errors = response.get("errors", [])
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        if not resp:
            raise Error("Unexpected situation, resp hasn't been initialized.")

        response = decode_json(response=resp, url=url)

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    @handle_relogin
    async def _post(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReachableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didn't respond before the timeout expired
        """
        await self.login()

        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)

        return await self._request(
            url=url, method=HTTPMethod.POST, headers=headers, timeout=timeout or self.default_timeout, payload=payload
        )

    @handle_relogin
    async def _get(self, url: str, headers: Optional[dict] = None, timeout: Optional[int] = None) -> httpx.Response:
        """Execute a HTTP GET with HTTPX.

        Raises:
            ServerNotReachableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        await self.login()

        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)

        return await self._request(
            url=url, method=HTTPMethod.GET, headers=headers, timeout=timeout or self.default_timeout
        )

    async def _request(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        response = await self._request_method(url=url, method=method, headers=headers, timeout=timeout, payload=payload)
        self._record(response)
        return response

    async def _default_request_method(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        params: Dict[str, Any] = {}
        if payload:
            params["json"] = payload

        proxy_config: Dict[str, Union[str, Dict[str, httpx.HTTPTransport]]] = {}
        if self.config.proxy:
            proxy_config["proxy"] = self.config.proxy
        elif self.config.proxy_mounts:
            proxy_config["mounts"] = {
                key: httpx.HTTPTransport(proxy=value)
                for key, value in self.config.proxy_mounts.dict(by_alias=True).items()
            }

        async with httpx.AsyncClient(
            **proxy_config,  # type: ignore[arg-type]
            verify=self.config.tls_ca_file if self.config.tls_ca_file else not self.config.tls_insecure,
        ) as client:
            try:
                response = await client.request(
                    method=method.value,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    **params,
                )
            except httpx.NetworkError as exc:
                raise ServerNotReachableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url, timeout=timeout) from exc

        return response

    async def refresh_login(self) -> None:
        if not self.refresh_token:
            return

        url = f"{self.address}/api/auth/refresh"
        response = await self._request(
            url=url,
            method=HTTPMethod.POST,
            headers={"content-type": "application/json", "Authorization": f"Bearer {self.refresh_token}"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        data = decode_json(response=response, url=url)
        self.access_token = data["access_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    async def login(self, refresh: bool = False) -> None:
        if not self.config.password_authentication:
            return

        if self.access_token and not refresh:
            return

        if self.refresh_token and refresh:
            try:
                await self.refresh_login()
                return
            except httpx.HTTPStatusError as exc:
                # If we got a 401 while trying to refresh a token we must restart the authentication process
                # Other status codes indicate other errors
                if exc.response.status_code != 401:
                    response = exc.response.json()
                    errors = response.get("errors")
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        url = f"{self.address}/api/auth/login"
        response = await self._request(
            url=url,
            method=HTTPMethod.POST,
            payload={"username": self.config.username, "password": self.config.password},
            headers={"content-type": "application/json"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        data = decode_json(response=response, url=url)
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    async def query_gql_query(
        self,
        name: str,
        variables: Optional[dict] = None,
        update_group: bool = False,
        subscribers: Optional[List[str]] = None,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Dict:
        url = f"{self.address}/api/query/{name}"
        url_params = copy.deepcopy(params or {})
        headers = copy.copy(self.headers or {})

        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        if branch_name:
            url_params["branch"] = branch_name
        if at:
            url_params["at"] = at

        if subscribers:
            url_params["subscribers"] = subscribers

        url_params["update_group"] = str(update_group).lower()

        if url_params:
            url_params_str = []
            for key, value in url_params.items():
                if isinstance(value, (list)):
                    for item in value:
                        url_params_str.append(f"{key}={item}")
                else:
                    url_params_str.append(f"{key}={value}")

            url += "?" + "&".join(url_params_str)

        payload = {}
        if variables:
            payload["variables"] = variables

        resp = await self._post(
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout or self.default_timeout,
        )

        if raise_for_error:
            resp.raise_for_status()

        return decode_json(response=resp, url=url)

    async def get_diff_summary(
        self,
        branch: str,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> List[NodeDiff]:
        query = """
            query {
                DiffSummary {
                    branch
                    id
                    kind
                    action
                    display_label
                    elements {
                        element_type
                        name
                        action
                        summary {
                            added
                            updated
                            removed
                        }
                        ... on DiffSummaryElementRelationshipMany {
                            peers {
                                action
                                summary {
                                    added
                                    updated
                                    removed
                                }
                            }
                        }
                    }
                }
            }
        """
        response = await self.execute_graphql(
            query=query, branch_name=branch, timeout=timeout, tracker=tracker, raise_for_error=raise_for_error
        )
        return response["DiffSummary"]

    async def allocate_next_ip_address(
        self,
        resource_pool: InfrahubNode,
        identifier: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        branch: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Optional[InfrahubNode]:
        """Allocate a new IP address by using the provided resource pool.

        Args:
            resource_pool (InfrahubNode): Node corresponding to the pool to allocate resources from.
            identifier (str, optional): Value to perform idempotent allocation, the same resource will be returned for a given identifier.
            data (dict, optional): A key/value map to use to set attributes values on the allocated address.
            branch (str, optional): Name of the branch to allocate from. Defaults to default_branch.
            timeout (int, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            tracker (str, optional): The offset for pagination.
            raise_for_error (bool, optional): The limit for pagination.
        Returns:
            InfrahubNode: Node corresponding to the allocated resource.
        """
        if resource_pool.get_kind() != "CoreIPAddressPool":
            raise ValueError("resource_pool is not an IP address pool")

        branch = branch or self.default_branch
        mutation_name = "IPAddressPoolGetResource"

        query = self._build_ip_address_allocation_query(
            resource_pool_id=resource_pool.id, identifier=identifier, data=data
        )
        response = await self.execute_graphql(
            query=query,
            branch_name=branch,
            timeout=timeout,
            tracker=tracker,
            raise_for_error=raise_for_error,
            variables={"data": data},
        )

        if response[mutation_name]["ok"]:
            resource_details = response[mutation_name]["node"]
            return await self.get(kind=resource_details["kind"], id=resource_details["id"], branch=branch)
        return None

    async def allocate_next_ip_prefix(
        self,
        resource_pool: InfrahubNode,
        identifier: Optional[str] = None,
        prefix_length: Optional[int] = None,
        member_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        branch: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Optional[InfrahubNode]:
        """Allocate a new IP prefix by using the provided resource pool.

        Args:
            resource_pool (InfrahubNode): Node corresponding to the pool to allocate resources from.
            identifier (str, optional): Value to perform idempotent allocation, the same resource will be returned for a given identifier.
            prefix_length (int, optional): Length of the prefix to allocate.
            member_type (str, optional): Member type of the prefix to allocate.
            data (dict, optional): A key/value map to use to set attributes values on the allocated prefix.
            branch (str, optional): Name of the branch to allocate from. Defaults to default_branch.
            timeout (int, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            tracker (str, optional): The offset for pagination.
            raise_for_error (bool, optional): The limit for pagination.
        Returns:
            InfrahubNode: Node corresponding to the allocated resource.
        """
        if resource_pool.get_kind() != "CoreIPPrefixPool":
            raise ValueError("resource_pool is not an IP prefix pool")

        branch = branch or self.default_branch
        mutation_name = "IPPrefixPoolGetResource"

        query = self._build_ip_prefix_allocation_query(
            resource_pool_id=resource_pool.id,
            identifier=identifier,
            prefix_length=prefix_length,
            member_type=member_type,
            data=data,
        )
        response = await self.execute_graphql(
            query=query,
            branch_name=branch,
            timeout=timeout,
            tracker=tracker,
            raise_for_error=raise_for_error,
            variables={"data": data},
        )

        if response[mutation_name]["ok"]:
            resource_details = response[mutation_name]["node"]
            return await self.get(kind=resource_details["kind"], id=resource_details["id"], branch=branch)
        return None

    async def create_batch(self, return_exceptions: bool = False) -> InfrahubBatch:
        return InfrahubBatch(semaphore=self.concurrent_execution_limit, return_exceptions=return_exceptions)

    async def get_list_repositories(
        self, branches: Optional[Dict[str, BranchData]] = None, kind: str = "CoreGenericRepository"
    ) -> Dict[str, RepositoryData]:
        if not branches:
            branches = await self.branch.all()  # type: ignore

        branch_names = sorted(branches.keys())  # type: ignore

        batch = await self.create_batch()
        for branch_name in branch_names:
            batch.add(
                task=self.all,
                kind=kind,
                branch=branch_name,
                fragment=True,
                include=["id", "name", "location", "commit", "ref"],
            )

        responses = []
        async for _, response in batch.execute():
            responses.append(response)

        repositories = {}

        for branch_name, response in zip(branch_names, responses):
            for repository in response:
                repo_name = repository.name.value
                if repo_name not in repositories:
                    repositories[repo_name] = RepositoryData(
                        repository=repository,
                        branches={},
                    )

                repositories[repo_name].branches[branch_name] = repository.commit.value

        return repositories

    async def repository_update_commit(
        self, branch_name: str, repository_id: str, commit: str, is_read_only: bool = False
    ) -> bool:
        variables = {"repository_id": str(repository_id), "commit": str(commit)}
        await self.execute_graphql(
            query=get_commit_update_mutation(is_read_only=is_read_only),
            variables=variables,
            branch_name=branch_name,
            tracker="mutation-repository-update-commit",
        )

        return True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type is None and self.mode == InfrahubClientMode.TRACKING:
            await self.group_context.update_group()

        self.mode = InfrahubClientMode.DEFAULT


class InfrahubClientSync(BaseClient):
    group_context: InfrahubGroupContextSync

    def _initialize(self) -> None:
        self.schema = InfrahubSchemaSync(self)
        self.branch = InfrahubBranchManagerSync(self)
        self.object_store = ObjectStoreSync(self)
        self.store = NodeStoreSync()
        self._request_method: SyncRequester = self.config.sync_requester or self._default_request_method
        self.group_context = InfrahubGroupContextSync(self)

    @classmethod
    def init(
        cls,
        address: str = "",
        config: Optional[Union[Config, Dict[str, Any]]] = None,
    ) -> InfrahubClientSync:
        return cls(address=address, config=config)

    def create(
        self,
        kind: str,
        data: Optional[dict] = None,
        branch: Optional[str] = None,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        if not data and not kwargs:
            raise ValueError("Either data or a list of keywords but be provided")

        return InfrahubNodeSync(client=self, schema=schema, branch=branch, data=data or kwargs)

    def delete(self, kind: str, id: str, branch: Optional[str] = None) -> None:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch, data={"id": id})
        node.delete()

    def create_batch(self, return_exceptions: bool = False) -> InfrahubBatch:
        raise NotImplementedError("This method hasn't been implemented in the sync client yet.")

    def clone(self) -> InfrahubClientSync:
        """Return a cloned version of the client using the same configuration"""
        return InfrahubClientSync(config=self.config)

    def execute_graphql(
        self,
        query: str,
        variables: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[Union[str, Timestamp]] = None,
        timeout: Optional[int] = None,
        raise_for_error: bool = True,
        tracker: Optional[str] = None,
    ) -> Dict:
        """Execute a GraphQL query (or mutation).
        If retry_on_failure is True, the query will retry until the server becomes reacheable.

        Args:
            query (str): GraphQL Query to execute, can be a query or a mutation
            variables (dict, optional): Variables to pass along with the GraphQL query. Defaults to None.
            branch_name (str, optional): Name of the branch on which the query will be executed. Defaults to None.
            at (str, optional): Time when the query should be executed. Defaults to None.
            timeout (int, optional): Timeout in second for the query. Defaults to None.
            raise_for_error (bool, optional): Flag to indicate that we need to raise an exception if the response has some errors. Defaults to True.
        Raises:
            GraphQLError: When an error occurs during the execution of the GraphQL query or mutation.

        Returns:
            dict: The result of the GraphQL query or mutation.
        """

        url = self._graphql_url(branch_name=branch_name, at=at)

        payload: Dict[str, Union[str, dict]] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = copy.copy(self.headers or {})
        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        self._echo(url=url, query=query, variables=variables)

        retry = True
        resp = None
        while retry:
            retry = self.retry_on_failure
            try:
                resp = self._post(url=url, payload=payload, headers=headers, timeout=timeout)

                if raise_for_error:
                    resp.raise_for_status()

                retry = False
            except ServerNotReachableError:
                if retry:
                    self.log.warning(
                        f"Unable to connect to {self.address}, will retry in {self.retry_delay} seconds .."
                    )
                    sleep(self.retry_delay)
                else:
                    self.log.error(f"Unable to connect to {self.address} .. ")
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in [401, 403]:
                    response = decode_json(response=exc.response, url=url)
                    errors = response.get("errors", [])
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        if not resp:
            raise Error("Unexpected situation, resp hasn't been initialized.")

        response = decode_json(response=resp, url=url)

        if "errors" in response:
            raise GraphQLError(errors=response["errors"], query=query, variables=variables)

        return response["data"]

        # TODO add a special method to execute mutation that will check if the method returned OK

    def all(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
    ) -> List[InfrahubNodeSync]:
        """Retrieve all nodes of a given kind

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.

        Returns:
            List[InfrahubNodeSync]: List of Nodes
        """
        return self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            offset=offset,
            limit=limit,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
        )

    def _process_nodes_and_relationships(
        self, response: Dict[str, Any], schema_kind: str, branch: str, prefetch_relationships: bool
    ) -> ProcessRelationsNodeSync:
        """Processes InfrahubNodeSync and their Relationships from the GraphQL query response.

        Args:
            response (Dict[str, Any]): The response from the GraphQL query.
            schema_kind (str): The kind of schema being queried.
            branch (str): The branch name.
            prefetch_relationships (bool): Flag to indicate whether to prefetch relationship data.

        Returns:
            ProcessRelationsNodeSync: A TypedDict containing two lists:
                - 'nodes': A list of InfrahubNodeSync objects representing the nodes processed.
                - 'related_nodes': A list of InfrahubNodeSync objects representing the related nodes
        """

        nodes: List[InfrahubNodeSync] = []
        related_nodes: List[InfrahubNodeSync] = []

        for item in response.get(schema_kind, {}).get("edges", []):
            node = InfrahubNodeSync.from_graphql(client=self, branch=branch, data=item)
            nodes.append(node)

            if prefetch_relationships:
                node._process_relationships(node_data=item, branch=branch, related_nodes=related_nodes)

        return ProcessRelationsNodeSync(nodes=nodes, related_nodes=related_nodes)

    def filters(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        populate_store: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        partial_match: bool = False,
        **kwargs: Any,
    ) -> List[InfrahubNodeSync]:
        """Retrieve nodes of a given kind based on provided filters.

        Args:
            kind (str): kind of the nodes to query
            at (Timestamp, optional): Time of the query. Defaults to Now.
            branch (str, optional): Name of the branch to query from. Defaults to default_branch.
            populate_store (bool, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            offset (int, optional): The offset for pagination.
            limit (int, optional): The limit for pagination.
            include (List[str], optional): List of attributes or relationships to include in the query.
            exclude (List[str], optional): List of attributes or relationships to exclude from the query.
            fragment (bool, optional): Flag to use GraphQL fragments for generic schemas.
            prefetch_relationships (bool, optional): Flag to indicate whether to prefetch related node data.
            partial_match (bool, optional): Allow partial match of filter criteria for the query.
            **kwargs (Any): Additional filter criteria for the query.

        Returns:
            List[InfrahubNodeSync]: List of Nodes that match the given filters.
        """
        schema = self.schema.get(kind=kind)

        branch = branch or self.default_branch
        if at:
            at = Timestamp(at)

        node = InfrahubNodeSync(client=self, schema=schema, branch=branch)
        filters = kwargs

        if filters:
            node.validate_filters(filters=filters)

        nodes: List[InfrahubNodeSync] = []
        related_nodes: List[InfrahubNodeSync] = []

        has_remaining_items = True
        page_number = 1

        while has_remaining_items:
            page_offset = (page_number - 1) * self.pagination_size

            query_data = InfrahubNodeSync(client=self, schema=schema, branch=branch).generate_query_data(
                offset=offset or page_offset,
                limit=limit or self.pagination_size,
                filters=filters,
                include=include,
                exclude=exclude,
                fragment=fragment,
                prefetch_relationships=prefetch_relationships,
                partial_match=partial_match,
            )
            query = Query(query=query_data)
            response = self.execute_graphql(
                query=query.render(),
                branch_name=branch,
                at=at,
                tracker=f"query-{str(schema.kind).lower()}-page{page_number}",
            )

            process_result: ProcessRelationsNodeSync = self._process_nodes_and_relationships(
                response=response, schema_kind=schema.kind, branch=branch, prefetch_relationships=prefetch_relationships
            )
            nodes.extend(process_result["nodes"])
            related_nodes.extend(process_result["related_nodes"])

            remaining_items = response[schema.kind].get("count", 0) - (page_offset + self.pagination_size)
            if remaining_items < 0 or offset is not None or limit is not None:
                has_remaining_items = False

            page_number += 1

        if populate_store:
            for node in nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)
            related_nodes = list(set(related_nodes))
            for node in related_nodes:
                if node.id:
                    self.store.set(key=node.id, node=node)

        return nodes

    def get(
        self,
        kind: str,
        at: Optional[Timestamp] = None,
        branch: Optional[str] = None,
        id: Optional[str] = None,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        populate_store: bool = False,
        fragment: bool = False,
        prefetch_relationships: bool = False,
        **kwargs: Any,
    ) -> InfrahubNodeSync:
        branch = branch or self.default_branch
        schema = self.schema.get(kind=kind, branch=branch)

        filters: MutableMapping[str, Any] = {}

        if id:
            if not is_valid_uuid(id) and isinstance(schema, NodeSchema) and schema.default_filter:
                filters[schema.default_filter] = id
            else:
                filters["ids"] = [id]
        elif kwargs:
            filters = kwargs
        else:
            raise ValueError("At least one filter must be provided to get()")

        results = self.filters(
            kind=kind,
            at=at,
            branch=branch,
            populate_store=populate_store,
            include=include,
            exclude=exclude,
            fragment=fragment,
            prefetch_relationships=prefetch_relationships,
            **filters,
        )  # type: ignore[arg-type]

        if len(results) == 0:
            raise NodeNotFoundError(branch_name=branch, node_type=kind, identifier=filters)
        if len(results) > 1:
            raise IndexError("More than 1 node returned")

        return results[0]

    def get_list_repositories(
        self, branches: Optional[Dict[str, BranchData]] = None, kind: str = "CoreGenericRepository"
    ) -> Dict[str, RepositoryData]:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    def query_gql_query(
        self,
        name: str,
        variables: Optional[dict] = None,
        update_group: bool = False,
        subscribers: Optional[List[str]] = None,
        params: Optional[dict] = None,
        branch_name: Optional[str] = None,
        at: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Dict:
        url = f"{self.address}/api/query/{name}"
        url_params = copy.deepcopy(params or {})
        headers = copy.copy(self.headers or {})

        if self.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        if branch_name:
            url_params["branch"] = branch_name
        if at:
            url_params["at"] = at
        if subscribers:
            url_params["subscribers"] = subscribers

        url_params["update_group"] = str(update_group).lower()

        if url_params:
            url_params_str = []
            for key, value in url_params.items():
                if isinstance(value, (list)):
                    for item in value:
                        url_params_str.append(f"{key}={item}")
                else:
                    url_params_str.append(f"{key}={value}")

            url += "?" + "&".join(url_params_str)

        payload = {}
        if variables:
            payload["variables"] = variables

        resp = self._post(
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout or self.default_timeout,
        )

        if raise_for_error:
            resp.raise_for_status()

        return decode_json(response=resp, url=url)

    def get_diff_summary(
        self,
        branch: str,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> List[NodeDiff]:
        query = """
            query {
                DiffSummary {
                    branch
                    id
                    kind
                    action
                    display_label
                    elements {
                        element_type
                        name
                        action
                        summary {
                            added
                            updated
                            removed
                        }
                        ... on DiffSummaryElementRelationshipMany {
                            peers {
                                action
                                summary {
                                    added
                                    updated
                                    removed
                                }
                            }
                        }
                    }
                }
            }
        """
        response = self.execute_graphql(
            query=query, branch_name=branch, timeout=timeout, tracker=tracker, raise_for_error=raise_for_error
        )
        return response["DiffSummary"]

    def allocate_next_ip_address(
        self,
        resource_pool: InfrahubNodeSync,
        identifier: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        branch: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Optional[InfrahubNodeSync]:
        """Allocate a new IP address by using the provided resource pool.

        Args:
            resource_pool (InfrahubNodeSync): Node corresponding to the pool to allocate resources from.
            identifier (str, optional): Value to perform idempotent allocation, the same resource will be returned for a given identifier.
            data (dict, optional): A key/value map to use to set attributes values on the allocated address.
            branch (str, optional): Name of the branch to allocate from. Defaults to default_branch.
            timeout (int, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            tracker (str, optional): The offset for pagination.
            raise_for_error (bool, optional): The limit for pagination.
        Returns:
            InfrahubNodeSync: Node corresponding to the allocated resource.
        """
        if resource_pool.get_kind() != "CoreIPAddressPool":
            raise ValueError("resource_pool is not an IP address pool")

        branch = branch or self.default_branch
        mutation_name = "IPAddressPoolGetResource"

        query = self._build_ip_address_allocation_query(
            resource_pool_id=resource_pool.id, identifier=identifier, data=data
        )
        response = self.execute_graphql(
            query=query,
            branch_name=branch,
            timeout=timeout,
            tracker=tracker,
            raise_for_error=raise_for_error,
            variables={"data": data},
        )

        if response[mutation_name]["ok"]:
            resource_details = response[mutation_name]["node"]
            return self.get(kind=resource_details["kind"], id=resource_details["id"], branch=branch)
        return None

    def allocate_next_ip_prefix(
        self,
        resource_pool: InfrahubNodeSync,
        identifier: Optional[str] = None,
        prefix_length: Optional[int] = None,
        member_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        branch: Optional[str] = None,
        timeout: Optional[int] = None,
        tracker: Optional[str] = None,
        raise_for_error: bool = True,
    ) -> Optional[InfrahubNodeSync]:
        """Allocate a new IP prefix by using the provided resource pool.

        Args:
            resource_pool (InfrahubNodeSync): Node corresponding to the pool to allocate resources from.
            identifier (str, optional): Value to perform idempotent allocation, the same resource will be returned for a given identifier.
            prefix_length (int, optional): Length of the prefix to allocate.
            member_type (str, optional): Member type of the prefix to allocate.
            data (dict, optional): A key/value map to use to set attributes values on the allocated prefix.
            branch (str, optional): Name of the branch to allocate from. Defaults to default_branch.
            timeout (int, optional): Flag to indicate whether to populate the store with the retrieved nodes.
            tracker (str, optional): The offset for pagination.
            raise_for_error (bool, optional): The limit for pagination.
        Returns:
            InfrahubNodeSync: Node corresponding to the allocated resource.
        """
        if resource_pool.get_kind() != "CoreIPPrefixPool":
            raise ValueError("resource_pool is not an IP prefix pool")

        branch = branch or self.default_branch
        mutation_name = "IPPrefixPoolGetResource"

        query = self._build_ip_prefix_allocation_query(
            resource_pool_id=resource_pool.id,
            identifier=identifier,
            prefix_length=prefix_length,
            member_type=member_type,
            data=data,
        )
        response = self.execute_graphql(
            query=query,
            branch_name=branch,
            timeout=timeout,
            tracker=tracker,
            raise_for_error=raise_for_error,
            variables={"data": data},
        )

        if response[mutation_name]["ok"]:
            resource_details = response[mutation_name]["node"]
            return self.get(kind=resource_details["kind"], id=resource_details["id"], branch=branch)
        return None

    def repository_update_commit(
        self, branch_name: str, repository_id: str, commit: str, is_read_only: bool = False
    ) -> bool:
        raise NotImplementedError(
            "This method is deprecated in the async client and won't be implemented in the sync client."
        )

    @handle_relogin_sync
    def _get(self, url: str, headers: Optional[dict] = None, timeout: Optional[int] = None) -> httpx.Response:
        """Execute a HTTP GET with HTTPX.

        Raises:
            ServerNotReachableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        self.login()

        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)

        return self._request(url=url, method=HTTPMethod.GET, headers=headers, timeout=timeout or self.default_timeout)

    @handle_relogin_sync
    def _post(
        self,
        url: str,
        payload: dict,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> httpx.Response:
        """Execute a HTTP POST with HTTPX.

        Raises:
            ServerNotReachableError if we are not able to connect to the server
            ServerNotResponsiveError if the server didnd't respond before the timeout expired
        """
        self.login()

        headers = headers or {}
        base_headers = copy.copy(self.headers or {})
        headers.update(base_headers)

        return self._request(
            url=url, method=HTTPMethod.POST, payload=payload, headers=headers, timeout=timeout or self.default_timeout
        )

    def _request(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        response = self._request_method(url=url, method=method, headers=headers, timeout=timeout, payload=payload)
        self._record(response)
        return response

    def _default_request_method(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        params: Dict[str, Any] = {}
        if payload:
            params["json"] = payload

        proxy_config: Dict[str, Union[str, Dict[str, httpx.HTTPTransport]]] = {}
        if self.config.proxy:
            proxy_config["proxy"] = self.config.proxy
        elif self.config.proxy_mounts:
            proxy_config["mounts"] = {
                key: httpx.HTTPTransport(proxy=value)
                for key, value in self.config.proxy_mounts.dict(by_alias=True).items()
            }

        with httpx.Client(
            **proxy_config,  # type: ignore[arg-type]
            verify=self.config.tls_ca_file if self.config.tls_ca_file else not self.config.tls_insecure,
        ) as client:
            try:
                response = client.request(
                    method=method.value,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    **params,
                )
            except httpx.NetworkError as exc:
                raise ServerNotReachableError(address=self.address) from exc
            except httpx.ReadTimeout as exc:
                raise ServerNotResponsiveError(url=url, timeout=timeout) from exc

        return response

    def refresh_login(self) -> None:
        if not self.refresh_token:
            return

        url = f"{self.address}/api/auth/refresh"
        response = self._request(
            url=url,
            method=HTTPMethod.POST,
            headers={"content-type": "application/json", "Authorization": f"Bearer {self.refresh_token}"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        data = decode_json(response=response, url=url)
        self.access_token = data["access_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    def login(self, refresh: bool = False) -> None:
        if not self.config.password_authentication:
            return

        if self.access_token and not refresh:
            return

        if self.refresh_token and refresh:
            try:
                self.refresh_login()
                return
            except httpx.HTTPStatusError as exc:
                # If we got a 401 while trying to refresh a token we must restart the authentication process
                # Other status codes indicate other errors
                if exc.response.status_code != 401:
                    response = exc.response.json()
                    errors = response.get("errors")
                    messages = [error.get("message") for error in errors]
                    raise AuthenticationError(" | ".join(messages)) from exc

        url = f"{self.address}/api/auth/login"
        response = self._request(
            url=url,
            method=HTTPMethod.POST,
            payload={"username": self.config.username, "password": self.config.password},
            headers={"content-type": "application/json"},
            timeout=self.default_timeout,
        )

        response.raise_for_status()
        data = decode_json(response=response, url=url)
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.headers["Authorization"] = f"Bearer {self.access_token}"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type is None and self.mode == InfrahubClientMode.TRACKING:
            self.group_context.update_group()

        self.mode = InfrahubClientMode.DEFAULT
