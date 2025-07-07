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


class AllowanceAttribute(MapAttribute):
    time_range = UnicodeAttribute(null=True)
    job_balance = NumberAttribute(null=True)
    balance_exhaustion_model = UnicodeAttribute(null=True)


class RightsizerLicensesApplicationMeta(MapAttribute):
    cloud = UnicodeAttribute(null=True)
    algorithm_map = MapAttribute(null=True)
    license_key = UnicodeAttribute(null=True)
    tenant_license_key = UnicodeAttribute(null=True)
    expiration = UnicodeAttribute(null=True)
    latest_sync = UnicodeAttribute(null=True)
    allowance = AllowanceAttribute(null=True)
    customers = MapAttribute(null=True)


class RightSizerDojoApplicationMeta(MapAttribute):
    host = UnicodeAttribute(null=True)
    port = NumberAttribute(null=True)
    protocol = UnicodeAttribute(null=True)
    stage = UnicodeAttribute(null=True)
