from __future__ import annotations

import os
import os.path
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import toml
from pydantic import BaseSettings, Field, ValidationError, root_validator

from infrahub_client import generate_uuid

SETTINGS: Settings = None

VALID_DATABASE_NAME_REGEX = r"^[a-z][a-z0-9\.]+$"
THIRTY_DAYS_IN_SECONDS = 3600 * 24 * 30


class DatabaseType(str, Enum):
    NEO4J = "neo4j"
    MEMGRAPH = "memgraph"


class StorageDriver(str, Enum):
    LOCAL = "local"


class TraceExporterType(str, Enum):
    CONSOLE = "console"
    OTLP = "otlp"
    # JAEGER = "jaeger"
    # ZIPKIN = "zipkin"


class TraceTransportProtocol(str, Enum):
    GRPC = "grpc"
    HTTP_PROTOBUF = "http/protobuf"
    # HTTP_JSON = "http/json"


class MainSettings(BaseSettings):
    default_branch: str = "main"
    # default_account: str = "default"
    # default_account_perm: str = "CAN_READ"

    internal_address: str = "http://localhost:8000"
    allow_anonymous_access: bool = Field(
        default=True, description="Indicates if the system allows anonymous read access"
    )

    class Config:
        env_prefix = "INFRAHUB_"
        case_sensitive = False


class StorageSettings(BaseSettings):
    driver: StorageDriver = StorageDriver.LOCAL
    settings: Optional[Dict[str, str]]

    class Config:
        case_sensitive = False
        fields = {
            "driver": {"env": "INFRAHUB_STORAGE_DRIVER"},
        }


class DatabaseSettings(BaseSettings):
    db_type: DatabaseType = DatabaseType.MEMGRAPH
    protocol: str = "bolt"
    username: str = "neo4j"
    password: str = "admin"
    address: str = "localhost"
    port: int = 7687
    database: Optional[str] = Field(regex=VALID_DATABASE_NAME_REGEX, description="Name of the database")
    imposed_query_limit: int = Field(
        1000, description="The max number of records to fetch in a single query before performing internal pagination."
    )

    class Config:
        """Additional parameters to automatically map environment variables to some settings."""

        fields = {
            "db_type": {"env": "INFRAHUB_DB_TYPE"},
            "protocol": {"env": "NEO4J_PROTOCOL"},
            "username": {"env": "NEO4J_USERNAME"},
            "password": {"env": "NEO4J_PASSWORD"},
            "address": {"env": "NEO4J_ADDRESS"},
            "port": {"env": "NEO4J_PORT"},
            "database": {"env": "NEO4J_DATABASE"},
        }

    @root_validator(pre=False)
    def default_database_name(cls, values):  # pylint: disable=no-self-argument
        if not values.get("database", None):
            values["database"] = values["db_type"].value
        return values


class BrokerSettings(BaseSettings):
    enable: bool = True
    tls_enabled: bool = Field(default=False, description="Indicates if TLS is enabled for the connection")
    username: str = "infrahub"
    password: str = "infrahub"
    address: str = "localhost"
    port: Optional[int] = Field(
        default=None, min=1, max=65535, description="Specified if running on a non default port."
    )
    namespace: str = "infrahub"

    @property
    def service_port(self) -> int:
        default_ports: Dict[bool, int] = {True: 5671, False: 5672}
        return self.port or default_ports[self.tls_enabled]

    class Config:
        env_prefix = "INFRAHUB_BROKER_"
        case_sensitive = False


class CacheSettings(BaseSettings):
    enable: bool = True
    address: str = "localhost"
    port: Optional[int] = Field(
        default=None, min=1, max=65535, description="Specified if running on a non default port (6379)"
    )
    database: int = Field(default=0, min=0, max=15, description="Id of the database to use")

    @property
    def service_port(self) -> int:
        default_ports: int = 6379
        return self.port or default_ports

    class Config:
        env_prefix = "INFRAHUB_CACHE_"
        case_sensitive = False


class ApiSettings(BaseSettings):
    cors_allow_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


class GitSettings(BaseSettings):
    repositories_directory: str = "repositories"


class MiscellaneousSettings(BaseSettings):
    print_query_details: bool = False
    start_background_runner: bool = True


class RemoteLoggingSettings(BaseSettings):
    enable: bool = False
    frontend_dsn: Optional[str] = None
    api_server_dsn: Optional[str] = None
    git_agent_dsn: Optional[str] = None

    class Config:
        env_prefix = "INFRAHUB_LOGGING_REMOTE_"
        case_sensitive = False


class LoggingSettings(BaseSettings):
    remote: RemoteLoggingSettings = RemoteLoggingSettings()


class AnalyticsSettings(BaseSettings):
    enable: bool = True
    address: Optional[str] = None
    api_key: Optional[str] = None

    class Config:
        env_prefix = "INFRAHUB_ANALYTICS_"
        case_sensitive = False


class ExperimentalFeaturesSettings(BaseSettings):
    pull_request: bool = False
    ignore_authentication_requirements: bool = Field(
        default=True,
        description="If set to true operations that would have been denied due to lack of authentication still works.",
    )

    class Config:
        env_prefix = "INFRAHUB_EXPERIMENTAL_"
        case_sensitive = False


class SecuritySettings(BaseSettings):
    access_token_lifetime: int = Field(default=3600, description="Lifetime of access token in seconds")
    refresh_token_lifetime: int = Field(
        default=THIRTY_DAYS_IN_SECONDS, description="Lifetime of refresh token in seconds"
    )
    secret_key: str = Field(
        default_factory=generate_uuid, description="The secret key used to validate authentication tokens"
    )
    initial_admin_password: str = Field(default="infrahub", description="The initial password for the admin user")
    initial_admin_token: Optional[str] = Field(
        default=None, description="An optional initial token for the admin account."
    )

    class Config:
        env_prefix = "INFRAHUB_SECURITY_"
        case_sensitive = False


class TraceSettings(BaseSettings):
    enable: bool = Field(default=False)
    insecure: bool = Field(
        default=True, description="Use insecure connection (HTTP) if True, otherwise use secure connection (HTTPS)"
    )
    exporter_type: TraceExporterType = Field(
        default=TraceExporterType.CONSOLE, description="Type of exporter to be used for tracing"
    )
    exporter_protocol: TraceTransportProtocol = Field(
        default=TraceTransportProtocol.GRPC, description="Protocol to be used for exporting traces"
    )
    exporter_endpoint: str = Field(default=None, description="OTLP endpoint for exporting traces")
    exporter_port: Optional[int] = Field(
        default=None, min=1, max=65535, description="Specified if running on a non default port (4317)"
    )

    @property
    def service_port(self) -> int:
        if self.exporter_protocol == TraceTransportProtocol.GRPC:
            default_port = 4317
        elif self.exporter_protocol == TraceTransportProtocol.HTTP_PROTOBUF:
            default_port = 4318
        else:
            default_port = 4317

        return self.exporter_port or default_port

    @property
    def trace_endpoint(self) -> str:
        if not self.exporter_endpoint:
            return None
        if self.insecure:
            scheme = "http://"
        else:
            scheme = "https://"
        endpoint = str(self.exporter_endpoint) + ":" + str(self.service_port)

        if self.exporter_protocol == TraceTransportProtocol.HTTP_PROTOBUF:
            endpoint += "/v1/traces"

        return scheme + endpoint

    class Config:
        env_prefix = "INFRAHUB_TRACE_"
        case_sensitive = False


class Settings(BaseSettings):
    """Main Settings Class for the project."""

    main: MainSettings = MainSettings()
    api: ApiSettings = ApiSettings()
    git: GitSettings = GitSettings()
    database: DatabaseSettings = DatabaseSettings()
    broker: BrokerSettings = BrokerSettings()
    cache: CacheSettings = CacheSettings()
    miscellaneous: MiscellaneousSettings = MiscellaneousSettings()
    logging: LoggingSettings = LoggingSettings()
    analytics: AnalyticsSettings = AnalyticsSettings()
    security: SecuritySettings = SecuritySettings()
    storage: StorageSettings = StorageSettings()
    trace: TraceSettings = TraceSettings()
    experimental_features: ExperimentalFeaturesSettings = ExperimentalFeaturesSettings()


def load(config_file_name="infrahub.toml", config_data=None):
    """Load configuration.

    Configuration is loaded from a config file in toml format that contains the settings,
    or from a dictionary of those settings passed in as "config_data"
    """
    global SETTINGS  # pylint: disable=global-statement

    if config_data:
        SETTINGS = Settings(**config_data)
        return

    if os.path.exists(config_file_name):
        config_string = Path(config_file_name).read_text(encoding="utf-8")
        config_tmp = toml.loads(config_string)

        SETTINGS = Settings(**config_tmp)
        return

    SETTINGS = Settings()


def load_and_exit(config_file_name="infrahub.toml", config_data=None):
    """Calls load, but wraps it in a try except block.

    This is done to handle a ValidationErorr which is raised when settings are specified but invalid.
    In such cases, a message is printed to the screen indicating the settings which don't pass validation.

    Args:
        config_file_name (str, optional): [description]. Defaults to "pyproject.toml".
        config_data (dict, optional): [description]. Defaults to None.
    """
    try:
        load(config_file_name=config_file_name, config_data=config_data)
    except ValidationError as err:
        print(f"Configuration not valid, found {len(err.errors())} error(s)")
        for error in err.errors():
            print(f"  {'/'.join(error['loc'])} | {error['msg']} ({error['type']})")
        sys.exit(1)
