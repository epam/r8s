from pynamodb.attributes import MapAttribute, UnicodeAttribute, \
    ListAttribute, BooleanAttribute


class ShapeRule(MapAttribute):
    rule_id = UnicodeAttribute(null=True)
    cloud = UnicodeAttribute(null=True)
    action = UnicodeAttribute(null=True)
    condition = UnicodeAttribute(null=True)
    field = UnicodeAttribute(null=True)
    value = UnicodeAttribute(null=True)


class LicensesParentMeta(MapAttribute):
    shape_rules = ListAttribute(of=ShapeRule, null=True, default=[])


class DojoParentMeta(MapAttribute):
    scan_type = UnicodeAttribute(attr_name='st', null=True)
    product_type = UnicodeAttribute(attr_name='pt', null=True)
    product = UnicodeAttribute(attr_name='p', null=True)
    engagement = UnicodeAttribute(attr_name='e', null=True)
    test = UnicodeAttribute(attr_name='t', null=True)
    send_after_job = BooleanAttribute(attr_name='saj', null=True)

    @staticmethod
    def build():
        return DojoParentMeta(
            scan_type='Generic Findings Import',
            product_type='RightSizer',
            product='{tenant_name}',
            engagement='RightSizer Main',
            test='{job_id}',
            send_after_job=True
        )

    def as_dict(self) -> dict:
        """
        Dict that is stored to DB
        :return:
        """
        return {
            'st': self.scan_type,
            'pt': self.product_type,
            'p': self.product,
            'e': self.engagement,
            't': self.test,
            'saj': self.send_after_job
        }