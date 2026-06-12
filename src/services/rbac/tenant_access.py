from models.policy import Policy, EFFECT_ALLOW, EFFECT_DENY


class PolicyStruct:
    __slots__ = ('name', 'effect', 'permissions', 'tenants')

    def __init__(self, policy: Policy):
        self.name: str = policy.name
        self.effect: str = policy.effect or EFFECT_ALLOW
        self.permissions: frozenset = frozenset(policy.permissions or [])
        self.tenants: tuple = tuple(policy.tenants or [])

    def touches(self, permission: str) -> bool:
        """Returns True if this policy explicitly lists the given permission."""
        return permission in self.permissions

    def forbids(self, permission: str) -> bool:
        """Fast-fail: a DENY policy with wildcard or unscoped tenants that
        touches this permission forbids it unconditionally → immediate 403."""
        return (self.effect == EFFECT_DENY
                and self.touches(permission)
                and (not self.tenants or '*' in self.tenants))

    def allows(self, permission: str) -> bool:
        """Returns True if this ALLOW policy grants the permission."""
        return self.effect == EFFECT_ALLOW and self.touches(permission)


class TenantsAccessPayload:
    ALL = object()

    __slots__ = '_names', '_allowed_flag'

    def __init__(self, names: tuple, allowed: bool):
        """
        Encodes which tenants are accessible for a permission.
        - allowed=True,  names={T1, T2}: only T1 and T2 are allowed
        - allowed=False, names={T1}:     all tenants except T1 are allowed
        - allowed=False, names=():       all tenants allowed (build_allowing_all)
        - allowed=True,  names=():       no tenants allowed  (build_denying_all)
        """
        self._names = names
        self._allowed_flag = allowed

    def __repr__(self) -> str:
        return (f'{self.__class__.__name__}'
                f'(names={self._names}, allowed={self._allowed_flag})')

    @classmethod
    def build_denying_all(cls) -> 'TenantsAccessPayload':
        return cls(names=(), allowed=True)

    def is_allowed_for(self, tenant_name: str) -> bool:
        _mention = tenant_name in self._names
        _allowed = self._allowed_flag
        return _mention and _allowed or not _mention and not _allowed

    def is_allowed_for_all_tenants(self) -> bool:
        return not self._names and not self._allowed_flag

    def is_denying_all(self) -> bool:
        return bool(self._allowed_flag) and not self._names

    def restrict_to(self, tenant_names: set) -> 'TenantsAccessPayload':
        """Returns a new payload restricted to only the given tenant names.
        Used to apply user-level tenant restrictions on top of policy-based access.
        An empty set results in denying all."""
        if not tenant_names:
            return TenantsAccessPayload.build_denying_all()
        allowed, denied = self.allowed_denied()
        if allowed is self.ALL:
            effective = tenant_names - set(denied)
        else:
            effective = set(allowed) & tenant_names
        return TenantsAccessPayload(tuple(effective), True)

    def allowed_denied(self) -> tuple:
        """Returns (allowed, denied) where allowed may be TenantsAccessPayload.ALL.

        Usage:
            allowed, denied = tap.allowed_denied()
            if allowed is TenantsAccessPayload.ALL:
                items = [x for x in all_items if x not in denied]
            else:
                items = [x for x in all_items if x in allowed]
        """
        if self._allowed_flag:
            return self._names, ()
        return self.ALL, self._names


class TenantAccess:
    __slots__ = '_allow_policies', '_deny_policies'

    def __init__(self):
        self._allow_policies: list = []
        self._deny_policies: list = []

    def add(self, policy: PolicyStruct) -> None:
        if policy.effect == EFFECT_ALLOW:
            self._allow_policies.append(policy)
        else:
            self._deny_policies.append(policy)

    def resolve_payload(self, permission: str) -> TenantsAccessPayload:
        """Computes which tenants are accessible for the given permission
        by aggregating all ALLOW and DENY policies in order."""
        names, flag = set(), True  # start state: denying_all

        for policy in self._allow_policies:
            if not policy.touches(permission):
                continue
            if not policy.tenants or '*' in policy.tenants:  # unscoped or wildcard = all tenants
                flag = False
                names.clear()
            else:
                if flag:
                    names.update(policy.tenants)
                else:
                    names.difference_update(policy.tenants)

        for policy in self._deny_policies:
            if not policy.touches(permission):
                continue
            if not policy.tenants or '*' in policy.tenants:  # unscoped or wildcard = all tenants
                flag = True
                names.clear()
            else:
                if flag:
                    names.difference_update(policy.tenants)
                else:
                    names.update(policy.tenants)

        return TenantsAccessPayload(tuple(names), flag)
