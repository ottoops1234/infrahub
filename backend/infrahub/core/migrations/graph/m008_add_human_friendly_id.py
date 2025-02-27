from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from typing_extensions import Self

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.path import SchemaPath

from ..schema.node_attribute_add import NodeAttributeAddMigration
from ..shared import InternalSchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration008(InternalSchemaMigration):
    name: str = "008_node_add_human_friendly_id"
    minimum_version: int = 7

    @classmethod
    def init(cls, *args: Any, **kwargs: Dict[str, Any]) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_node = internal_schema.get_node(name="SchemaNode")
        schema_generic = internal_schema.get_node(name="SchemaGeneric")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_node,
                previous_node_schema=schema_node,
                schema_path=SchemaPath(
                    schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
                ),
            ),
            NodeAttributeAddMigration(
                new_node_schema=schema_generic,
                previous_node_schema=schema_generic,
                schema_path=SchemaPath(
                    schema_kind="SchemaGeneric", path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
                ),
            ),
        ]
        return cls(*args, migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        return result
