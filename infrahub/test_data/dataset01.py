import logging

from infrahub.core.node import Node

# from infrahub.models import Device, Interface, Role, Status, Permission, Tag, IPAddress
# from infrahub.core.account import Account, AccountToken, Group

ROLES = ["spine", "leaf", "firewall", "server", "loopback"]

DEVICES = (
    ("spine1", "active", "MX480", "profile1", "spine", ["red", "green"]),
    ("spine2", "active", "MX480", "profile1", "spine", ["red", "blue", "green"]),
    ("leaf1", "active", "QFX5100", None, "leaf", ["red", "blue"]),
    ("leaf2", "maintenance", "QFX5100", "profile2", None, ["red", "blue", "green"]),
    ("leaf3", "active", "QFX5100", None, "leaf", ["blue", "green"]),
    ("web01", "active", "s-1vcpu-1gb-intel", None, "server", ["green"]),
    ("web02", "active", "s-1vcpu-1gb-intel", None, "server", ["green", "red"]),
    ("database01", "active", "s-1vcpu-1gb-intel", None, "server", ["green"]),
)

# DEVICE_PROFILES = (
#     ("profile1", "provisionning", "MX240", "spine"),
#     ("profile2", "provisionning", "QFX5200", "leaf"),
# )

PERMS = (
    ("device.name.all.read", "READ", "device.name.all"),
    ("device.name.all.write", "WRITE", "device.name.all"),
    ("device.status.all.read", "READ", "device.status.all"),
    ("device.status.all.write", "WRITE", "device.status.all"),
    ("device.description.all.read", "READ", "device.description.all"),
    ("device.description.all.write", "WRITE", "device.description.all"),
)

GROUPS = (
    (
        "Network Engineer",
        "network-engineer",
        (
            "device.name.all.read",
            "device.status.all.read",
            "device.description.all.read",
            "device.name.all.write",
            "device.status.all.write",
            "device.description.all.write",
        ),
    ),
    (
        "Operator",
        "operator",
        (
            "device.name.all.read",
            "device.status.all.read",
            "device.description.all.read",
            "device.description.all.write",
        ),
    ),
    ("Manager", "manager", ("device.name.all.read", "device.status.all.read", "device.description.all.read")),
)

ACCOUNTS = (
    ("ozzie", "USER", ("operator",)),
    ("nelly", "USER", ("network-engineer", "operator")),
    ("mary", "USER", ("manager",)),
)

INTERFACE_ROLES = {
    "spine": ["leaf", "leaf", "leaf", "leaf", "leaf", "leaf"],
    "leaf": ["spine", "spine", "spine", "spine", "server", "server"],
}

LOGGER = logging.getLogger("infrahub")


def load_data():

    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    groups_dict = {}
    accounts_dict = {}
    perms_dict = {}
    tags_dict = {}

    # for perm in PERMS:
    #     obj = Permission.init(name=perm[0], type=perm[1])
    #     obj.save()
    #     perms_dict[perm[0]] = obj

    #     # Associate the permissions with the right attr group
    #     grp = registry.attr_group[perm[2]]
    #     add_relationship(obj, grp, f"CAN_{obj.type.value}")

    #     LOGGER.info(f"Permission Created: {obj.name.value}")

    # # Import the existing groups into the dict
    # groups = Group.get_list()
    # for group in groups:
    #     groups_dict[group.slug.value] = group

    for group in GROUPS:
        obj = Node("Group").new(description=group[0], name=group[1]).save()
        groups_dict[group[1]] = obj
        LOGGER.info(f"Group Created: {obj.name.value}")

        # for perm_name in group[2]:
        #     perm = perms_dict[perm_name]

        #     # Associate the permissions with the right attr group
        #     add_relationship(obj, perm, f"HAS_PERM")

    # for account in ACCOUNTS:
    #     obj =  Node("Account").new(name=account[0], type=account[1]).save()
    #     accounts_dict[account[0]] = obj

    #     for group in account[2]:
    #         groups_dict[group].add_account(obj)

    #     LOGGER.info(f"Account Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & DeviceProfile
    # ------------------------------------------
    statuses_dict = {}
    roles_dict = {}
    device_profiles_dict = {}

    LOGGER.info(f"Creating Roles & Status")
    for role in ROLES:
        obj = Node("Role").new(description=role.title(), name=role).save()
        roles_dict[role] = obj
        LOGGER.info(f"Created Role: {role}")

    STATUSES = ["active", "provisionning", "maintenance"]
    for status in STATUSES:
        obj = Node("Status").new(description=status.title(), name=status).save()
        statuses_dict[status] = obj
        LOGGER.info(f"Created Status: {status}")

    TAGS = ["blue", "green", "red"]
    for tag in TAGS:
        obj = Node("Tag").new(name=tag).save()
        tags_dict[tag] = obj
        LOGGER.info(f"Created Tag: {tag}")

    active_status = statuses_dict["active"]
    role_loopback = roles_dict["loopback"]

    LOGGER.info(f"Creating Device")
    for idx, device in enumerate(DEVICES):

        status = statuses_dict[device[1]]

        profile_id = None
        # if device[3]:
        #     # profile = device_profiles_dict[device[3]]
        #     profile_id = device_profiles_dict[device[3]].id

        role_id = None
        if device[4]:
            role_id = roles_dict[device[4]].id
        obj = Node("Device").new(name=device[0], status=status.id, type=device[2], role=role_id)

        # # Connect tags
        # for tag_name in device[5]:
        #     tag = tags_dict[tag_name]
        #     obj.tags.add_peer(tag)

        obj.save()
        LOGGER.info(f"- Created Device: {device[0]}")

        # Add a special interface for spine1
        if device[0] == "spine1":
            intf = (
                Node("Interface")
                .new(
                    device="spine1",
                    name="Loopback0",
                    enabled=True,
                    status=active_status.id,
                    role=role_loopback.id,
                    speed=10000,
                )
                .save()
            )

            ip = Node("IPAddress").new(interface=intf, address=f"192.168.{idx}.10/24").save()

        if device[4] not in ["spine", "leaf"]:
            continue

        # Create and connect interfaces
        INTERFACES = ["Ethernet0", "Ethernet1", "Ethernet2"]
        for intf_idx, intf_name in enumerate(INTERFACES):

            intf_role = INTERFACE_ROLES[device[4]][intf_idx]
            intf_role_id = roles_dict[intf_role].id

            enabled = True
            if intf_idx in [0, 1]:
                enabled = False

            intf = (
                Node("Interface")
                .new(
                    device=obj,
                    name=intf_name,
                    speed=10000,
                    enabled=enabled,
                    status=active_status.id,
                    role=intf_role_id,
                )
                .save()
            )

            if intf_idx == 1:
                ip = Node("IPAddress").new(interface=intf, address=f"192.168.{idx}.{intf_idx}/24").save()
