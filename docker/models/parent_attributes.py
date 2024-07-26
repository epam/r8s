from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    ListAttribute


class ShapeRule(MapAttribute):
    rule_id = UnicodeAttribute(null=True)
    cloud = UnicodeAttribute(null=True)
    action = UnicodeAttribute(null=True)
    condition = UnicodeAttribute(null=True)
    field = UnicodeAttribute(null=True)
    value = UnicodeAttribute(null=True)


class LicensesParentMeta(MapAttribute):
    shape_rules = ListAttribute(of=ShapeRule, null=True, default=[])
