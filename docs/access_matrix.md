# Access Matrix

Syndicate RightSizer implements Attribute Based Access Model (ABAC) in order to grant granular access to required resources and actions
for users sticking to the 'least privilege' practice.
Once the Installation is deployed the 'System Administrator' also known as 'root' is available to configure the installation. 
This user is also able to create Customer's - the logically separated workspaces for clients. Once the Customer entity is created
the 'Customer Admin' is created to configure it as required as well as manage it's Identities and Access. It is bound by the Customer workspace 
and can not access other's Customers data. 

To perform a successful request to a specific endpoint three conditions must be satisfied:
1) A user must provide an authentication token
2) The user's role must contain a permission that is required by this endpoint
3) The endpoint must not be a system one. Those are only for system admin. They are always unavailable for standard users

## User Types

![Users Types](./assets/access_matric_users.png)

## Permissions List
Here is a list of all permissions available in the Syndicate RightSizer: 
```commandline
"r8s:algorithm:describe_algorithm",
"r8s:algorithm:create_algorithm",
"r8s:algorithm:update_algorithm",
"r8s:algorithm:remove_algorithm",
"r8s:storage:describe_storage",
"r8s:storage:create_storage",
"r8s:storage:update_storage",
"r8s:storage:remove_storage",
"r8s:iam:describe_policy",
"r8s:iam:create_policy",
"r8s:iam:update_policy",
"r8s:iam:remove_policy",
"r8s:iam:describe_role",
"r8s:iam:create_role",
"r8s:iam:update_role",
"r8s:iam:remove_role",
"r8s:job:describe_definition",
"r8s:job:create_definition",
"r8s:job:update_definition",
"r8s:job:remove_definition",
"r8s:job:describe_job",
"r8s:job:submit_job",
"r8s:job:terminate_job",
"r8s:job:describe_report",
"r8s:report:initiate_tenant_report",
"r8s:storage:describe_metrics",
"r8s:iam:describe_user",
"r8s:iam:create_user",
"r8s:iam:update_user_password",
"r8s:iam:delete_user",
"r8s:parent:describe_shape_rule",
"r8s:parent:create_shape_rule",
"r8s:parent:update_shape_rule",
"r8s:parent:remove_shape_rule",
"r8s:parent:describe_parent",
"r8s:parent:create_parent",
"r8s:parent:update_parent",
"r8s:parent:remove_parent",
"r8s:parent:dry_run_shape_rule",
"r8s:parent:describe_resize_insights",
"r8s:application:describe_application",
"r8s:application:create_application",
"r8s:application:update_application",
"r8s:application:remove_application",
"r8s:application:describe_group_policy",
"r8s:application:create_group_policy",
"r8s:application:update_group_policy",
"r8s:application:remove_group_policy",
"r8s:shape:describe_shape",
"r8s:shape:create_shape",
"r8s:shape:update_shape",
"r8s:shape:remove_shape",
"r8s:shape:describe_shape_price",
"r8s:shape:create_shape_price",
"r8s:shape:update_shape_price",
"r8s:shape:remove_shape_price",
"r8s:health_check:describe_health_check",
"r8s:recommendation:describe_recommendation",
"r8s:recommendation:update_recommendation",
"r8s:license:describe_license",
"r8s:license:delete_license",
"r8s:license:sync_license",
"r8s:setting:describe_lm_config",
"r8s:setting:create_lm_config",
"r8s:setting:delete_lm_config",
"r8s:setting:describe_lm_client",
"r8s:setting:create_lm_client",
"r8s:setting:delete_lm_client"
```

