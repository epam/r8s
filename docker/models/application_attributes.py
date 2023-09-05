from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    NumberAttribute


class ConnectionAttribute(MapAttribute):
    host = UnicodeAttribute(null=True)
    port = NumberAttribute(null=True)
    protocol = UnicodeAttribute(null=True)
    username = UnicodeAttribute(null=True)


class ApplicationMeta(MapAttribute):
    input_storage = UnicodeAttribute(null=True)
    output_storage = UnicodeAttribute(null=True)
    connection = ConnectionAttribute(null=True)
