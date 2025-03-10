from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    NumberAttribute, ListAttribute


class ConnectionAttribute(MapAttribute):
    host = UnicodeAttribute(null=True)
    port = NumberAttribute(null=True)
    protocol = UnicodeAttribute(null=True)
    username = UnicodeAttribute(null=True)


class RightsizerApplicationMeta(MapAttribute):
    input_storage = UnicodeAttribute(null=True)
    output_storage = UnicodeAttribute(null=True)
    connection = ConnectionAttribute(null=True)
    group_policies = ListAttribute(of=MapAttribute, null=True)


class RightsizerLicensesApplicationMeta(MapAttribute):
    cloud = UnicodeAttribute(null=True)
    algorithm_map = MapAttribute(null=True)
    license_key = UnicodeAttribute(null=True)
    tenants = ListAttribute(of=UnicodeAttribute, default=[])
