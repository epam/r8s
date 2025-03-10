GET_METHOD = 'GET'
POST_METHOD = 'POST'
PATCH_METHOD = 'PATCH'
DELETE_METHOD = 'DELETE'

ENDPOINT_PERMISSION_MAPPING = {
    '/algorithms/': {
        GET_METHOD: 'r8s:algorithm:describe_algorithm',
        POST_METHOD: 'r8s:algorithm:create_algorithm',
        PATCH_METHOD: 'r8s:algorithm:update_algorithm',
        DELETE_METHOD: 'r8s:algorithm:remove_algorithm'
    },

    '/storages/': {
        GET_METHOD: 'r8s:storage:describe_storage',
        POST_METHOD: 'r8s:storage:create_storage',
        PATCH_METHOD: 'r8s:storage:update_storage',
        DELETE_METHOD: 'r8s:storage:remove_storage'
    },
    '/jobs/': {
        GET_METHOD: 'r8s:job:describe_job',
        POST_METHOD: 'r8s:job:submit_job',
        DELETE_METHOD: 'r8s:job:terminate_job',
    },
    '/policies/': {
        GET_METHOD: 'r8s:iam:describe_policy',
        POST_METHOD: 'r8s:iam:create_policy',
        PATCH_METHOD: 'r8s:iam:update_policy',
        DELETE_METHOD: 'r8s:iam:remove_policy',
    },
    '/roles/': {
        GET_METHOD: 'r8s:iam:describe_role',
        POST_METHOD: 'r8s:iam:create_role',
        PATCH_METHOD: 'r8s:iam:update_role',
        DELETE_METHOD: 'r8s:iam:remove_role',
    },
    '/jobs/definitions/': {
        GET_METHOD: 'r8s:job:describe_definition',
        POST_METHOD: 'r8s:job:create_definition',
        PATCH_METHOD: 'r8s:job:update_definition',
        DELETE_METHOD: 'r8s:job:remove_definition',
    },
    '/reports/': {
        GET_METHOD: 'r8s:job:describe_report',
    },
    '/reports/mail/tenant/': {
        POST_METHOD: 'r8s:report:initiate_tenant_report'
    },
    '/storages/data/': {
        GET_METHOD: 'r8s:storage:describe_metrics',
    },
    '/users/': {
        GET_METHOD: 'r8s:iam:describe_user',
        PATCH_METHOD: 'r8s:iam:update_user_password',
        DELETE_METHOD: 'r8s:iam:delete_user'
    },
    '/signup/': {
        POST_METHOD: 'r8s:iam:create_user'
    },
    '/applications/': {
        GET_METHOD: 'r8s:application:describe_application',
        POST_METHOD: 'r8s:application:create_application',
        PATCH_METHOD: 'r8s:application:update_application',
        DELETE_METHOD: 'r8s:application:remove_application',
    },
    '/applications/policies/': {
        GET_METHOD: 'r8s:application:describe_group_policy',
        POST_METHOD: 'r8s:application:create_group_policy',
        PATCH_METHOD: 'r8s:application:update_group_policy',
        DELETE_METHOD: 'r8s:application:remove_group_policy',
    },
    '/applications/licenses/': {
        GET_METHOD: 'r8s:application:describe_application',
        POST_METHOD: 'r8s:application:create_application',
        PATCH_METHOD: 'r8s:application:update_application',
        DELETE_METHOD: 'r8s:application:remove_application',
    },
    '/applications/dojo/': {
        GET_METHOD: 'r8s:application:describe_dojo_application',
        POST_METHOD: 'r8s:application:create_dojo_application',
        PATCH_METHOD: 'r8s:application:update_dojo_application',
        DELETE_METHOD: 'r8s:application:remove_dojo_application',
    },
    '/parents/': {
        GET_METHOD: 'r8s:parent:describe_parent',
        POST_METHOD: 'r8s:parent:create_parent',
        PATCH_METHOD: 'r8s:parent:update_parent',
        DELETE_METHOD: 'r8s:parent:remove_parent',
    },
    '/parents/dojo/': {
        GET_METHOD: 'r8s:parent:describe_dojo_parent',
        POST_METHOD: 'r8s:parent:create_dojo_parent',
        PATCH_METHOD: 'r8s:parent:update_dojo_parent',
        DELETE_METHOD: 'r8s:parent:remove_dojo_parent',
    },
    '/parents/shape-rules/': {
        GET_METHOD: 'r8s:parent:describe_shape_rule',
        POST_METHOD: 'r8s:parent:create_shape_rule',
        PATCH_METHOD: 'r8s:parent:update_shape_rule',
        DELETE_METHOD: 'r8s:parent:remove_shape_rule',
    },
    '/parents/shape-rules/dry-run/': {
        GET_METHOD: 'r8s:parent:dry_run_shape_rule'
    },
    '/shapes/': {
        GET_METHOD: 'r8s:shape:describe_shape',
        POST_METHOD: 'r8s:shape:create_shape',
        PATCH_METHOD: 'r8s:shape:update_shape',
        DELETE_METHOD: 'r8s:shape:remove_shape',
    },
    '/shapes/prices/': {
        GET_METHOD: 'r8s:shape:describe_shape_price',
        POST_METHOD: 'r8s:shape:create_shape_price',
        PATCH_METHOD: 'r8s:shape:update_shape_price',
        DELETE_METHOD: 'r8s:shape:remove_shape_price',
    },
    '/health-check/': {
        POST_METHOD: 'r8s:health_check:describe_health_check',
    },
    '/recommendations/': {
        GET_METHOD: 'r8s:recommendation:describe_recommendation',
        PATCH_METHOD: 'r8s:recommendation:update_recommendation',
    },
    '/licenses/': {
        GET_METHOD: 'r8s:license:describe_license',
        DELETE_METHOD: 'r8s:license:delete_license',
    },
    '/licenses/sync/': {
        POST_METHOD: 'r8s:license:sync_license'
    },
    '/settings/license-manager/config': {
        GET_METHOD: 'r8s:setting:describe_lm_config',
        POST_METHOD: 'r8s:setting:create_lm_config',
        DELETE_METHOD: 'r8s:setting:delete_lm_config',
    },
    '/settings/license-manager/client': {
        GET_METHOD: 'r8s:setting:describe_lm_client',
        POST_METHOD: 'r8s:setting:create_lm_client',
        DELETE_METHOD: 'r8s:setting:delete_lm_client',
    }
}
