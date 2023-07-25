from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    ListAttribute


class ShapeRule(MapAttribute):
    rule_id = UnicodeAttribute(null=True)
    action = UnicodeAttribute(null=True)
    condition = UnicodeAttribute(null=True)
    field = UnicodeAttribute(null=True)
    value = UnicodeAttribute(null=True)


class ParentMeta(MapAttribute):
    cloud = UnicodeAttribute(null=True)
    algorithm = UnicodeAttribute(null=True)
    scope = UnicodeAttribute(null=True)
    shape_rules = ListAttribute(null=True, of=ShapeRule)
    license_key = UnicodeAttribute(null=True)
