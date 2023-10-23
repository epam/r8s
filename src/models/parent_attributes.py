from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    ListAttribute


class ShapeRule(MapAttribute):
    rule_id = UnicodeAttribute(null=True)
    cloud = UnicodeAttribute(null=True)
    action = UnicodeAttribute(null=True)
    condition = UnicodeAttribute(null=True)
    field = UnicodeAttribute(null=True)
    value = UnicodeAttribute(null=True)


class ParentMeta(MapAttribute):
    shape_rules = ListAttribute(of=ShapeRule, default=list)


class LicensesParentMeta(MapAttribute):
    cloud = UnicodeAttribute(null=True)
    algorithm = UnicodeAttribute(null=True)
    license_key = UnicodeAttribute(null=True)