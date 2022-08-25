infrastructure_models = {
    "nodes": [
        {
            "name": "device",
            "kind": "Device",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "type", "kind": "String"},
            ],
            "relationships": [
                {"name": "site", "peer": "Location", "cardinality": "one"},
                {"name": "status", "peer": "Status", "cardinality": "one"},
                {"name": "role", "peer": "Role", "cardinality": "one"},
                {"name": "interfaces", "peer": "Interface", "optional": True, "cardinality": "many"},
                {"name": "asn", "peer": "AutonomousSystem", "optional": True, "cardinality": "one"},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "interface",
            "kind": "Interface",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String"},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "speed", "kind": "Integer"},
                {"name": "enabled", "kind": "Boolean", "default_value": True},
            ],
            "relationships": [
                {"name": "status", "peer": "Status", "cardinality": "one"},
                {"name": "role", "peer": "Role", "cardinality": "one"},
                {"name": "device", "peer": "Device", "cardinality": "one"},
                {"name": "tags", "peer": "Tag", "optional": True, "cardinality": "many"},
                {"name": "ip_addresses", "peer": "IPAddress", "optional": True, "cardinality": "many"},
                {"name": "connected_circuit", "peer": "CircuitEndpoint", "optional": True, "cardinality": "one"},
                {"name": "connected_interface", "peer": "Interface", "optional": True, "cardinality": "one"},
            ],
        },
        {
            "name": "ipaddress",
            "kind": "IPAddress",
            "default_filter": "address__value",
            "branch": True,
            "attributes": [
                {"name": "address", "kind": "String"},
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "interface", "peer": "Interface", "cardinality": "one"},
            ],
        },
        {
            "name": "circuit",
            "kind": "Circuit",
            "default_filter": "circuit_id__value",
            "branch": True,
            "attributes": [
                {"name": "circuit_id", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "vendor_id", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "status", "peer": "Status", "cardinality": "one"},
                {"name": "role", "peer": "Role", "cardinality": "one"},
                {"name": "provider", "peer": "Organization", "cardinality": "one"},
                {"name": "endpoints", "peer": "CircuitEndpoint", "optional": True, "cardinality": "many"},
            ],
        },
        {
            "name": "circuit_endpoint",
            "kind": "CircuitEndpoint",
            "branch": True,
            "attributes": [
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "site", "peer": "Location", "cardinality": "one"},
                {"name": "circuit", "peer": "Circuit", "cardinality": "one"},
                {"name": "connected_interface", "peer": "Interface", "optional": True, "cardinality": "one"},
            ],
        },
        {
            "name": "autonomous_system",
            "kind": "AutonomousSystem",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "asn", "kind": "Integer", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "organization", "peer": "Organization", "cardinality": "one"},
            ],
        },
        {
            "name": "bgp_peer_group",
            "kind": "BGPPeerGroup",
            "default_filter": "name__value",
            "branch": True,
            "attributes": [
                {"name": "name", "kind": "String"},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "import_policies", "kind": "String", "optional": True},
                {"name": "export_policies", "kind": "String", "optional": True},
            ],
            "relationships": [
                {
                    "name": "local_as",
                    "identifier": "bgppeergroup__local_as",
                    "peer": "AutonomousSystem",
                    "optional": True,
                    "cardinality": "one",
                },
                {
                    "name": "remote_as",
                    "identifier": "bgppeergroup__remote_as",
                    "peer": "AutonomousSystem",
                    "optional": True,
                    "cardinality": "one",
                },
            ],
        },
        {
            "name": "bgp_session",
            "kind": "BGPSession",
            "default_filter": "asn__value",
            "branch": True,
            "attributes": [
                {"name": "type", "kind": "String"},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "import_policies", "kind": "String", "optional": True},
                {"name": "export_policies", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "status", "peer": "Status", "cardinality": "one"},
                {"name": "role", "peer": "Role", "cardinality": "one"},
                {
                    "name": "local_as",
                    "identifier": "bgpsession__local_as",
                    "peer": "AutonomousSystem",
                    "optional": True,
                    "cardinality": "one",
                },
                {
                    "name": "remote_as",
                    "identifier": "bgpsession__remote_as",
                    "peer": "AutonomousSystem",
                    "optional": True,
                    "cardinality": "one",
                },
                {
                    "name": "local_ip",
                    "identifier": "bgpsession__local_ip",
                    "peer": "IPAddress",
                    "optional": True,
                    "cardinality": "one",
                },
                {
                    "name": "remote_ip",
                    "identifier": "bgpsession__remote_ip",
                    "peer": "IPAddress",
                    "optional": True,
                    "cardinality": "one",
                },
                {"name": "device", "peer": "Device", "optional": True, "cardinality": "one"},
                {"name": "peer_group", "peer": "BGPPeerGroup", "optional": True, "cardinality": "one"},
                {"name": "peer_session", "peer": "BGPSession", "optional": True, "cardinality": "one"},
            ],
        },
    ]
}
