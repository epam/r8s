## Install

    pip install r8s/

## Configure user credentials

    r8s configure --api_link <R8s_Service_API_link>

    r8s login --username <username> --password <password>

## Commands
Available command groups:
```
- cleanup
- configure
- register
- login
- health-check
- policy:
    - add
    - describe
    - delete
    - update
- role:
    - add
    - describe
    - delete
    - update
- user:
    - describe
    - delete
    - update
- algorithm:
    - add
    - describe
    - delete
    - update_general_settings
    - update_clustering_settings
    - update_metric_format
    - update_recommendation_settings
- job:
    - submit
    - describe
    - terminate
- report:
    - download
    - general
    - initiate_tenant_mail_report
- storage:
    - add
    - describe
    - delete
    - update
    - describe_metrics
- application:
    - add
    - describe
    - delete
    - update
- application policies:
    - describe
    - delete
    - add_autoscaling
    - update_autoscaling
- parent:
    - add
    - describe
    - delete
    - describe_tenant_links
    - link_tenant
    - unlink_tenant
    - describe_resize_insights
- parent licenses:
    - add
    - describe
    - delete
- parent shape_rule:
    - add
    - describe
    - delete
    - update
    - dry_run
- shape:
    - add
    - describe
    - delete
    - update
- shape price:
    - add
    - describe
    - delete
    - update
- recommendation:
    - describe
    - update
```
### Commands

[`login`](#login) - Authenticates user to work with R8s.

[`register`](#register) - Creates new user.

[`configure`](#configure) - Configures r8s tool to work with R8s.

[`cleanup`](#cleanup) - Removes all the configuration data related to the tool.

[`health-check`](#health-check) - Performs system health check.

### Command groups

[`algorithm`](#algorithm) - Manages Algorithms Entity

[`storage`](#storage) - Manages Storage Entity

[`job`](#job) - Manages R8s Jobs

[`report`](#report) - Manages R8s reports

[`policy`](#policy) - Manages Policy Entity

[`role`](#role) - Manages Role Entity

[`user`](#user) - Manages User Entity

[`application`](#application) - Manages Application Entity

[`application policies`](#application-policies) - Manages Application Group Policy Entity

[`parent`](#parent) - Manages RIGHTSIZER Parent Entity

[`parent licenses`](#shape-rule) - Manages RIGHTSIZER_LICENSES Parent Entity

[`parent shape-rule`](#shape-rule) - Manages Parent Shape Rule Entity

[`shape`](#shape) - Manages Shape Entity

[`shape price`](#shape_price) - Manages Shape Price Entity

## Commands

### login

**Usage:**

    r8s login --username USERNAME --password PASSWORD

_Authenticates user to work with R8s. Pay attention that,
the password can be entered in an interactive mode_

`-u,--username` `TEXT` R8s user username. [Required]

`-p,--password` `TEXT` R8s user password. [Required]

### register

**Usage:**

    r8s register --username USERNAME --password PASSWORD --customer_id $CUSTOMER --role_name $ROLE_NAME

_Registers a user. Pay attention that,
the password can be entered in an interactive mode_

`-u,--username` `TEXT` R8s user username. [Required]

`-p,--password` `TEXT` R8s user password. [Required]

`-cid,--customer_id` `TEXT` R8s user customer. [Required]
`-rn,--role_name` `TEXT` R8s user role name. [Required]

### configure

**Usage:**

    r8s configure --api_link <R8s_API_link>

_Configures r8s tool to work with R8s._

`-api,--api_link` `TEXT` Link to the R8s host. [Required]

### cleanup

**Usage:**

    r8s cleanup

_Removes all the configuration data related to the tool._

### health-check

**Usage:**

    r8s health-check --check_type $TYPE1 --check_type $TYPE2

_Performs system health check._
`-t,--check_type` `[APPLICATION|PARENT|STORAGE|SHAPE|OPERATION_MODE]` List of check types to execute.

## Command groups

----------------------------------------

### `policy`

**Usage:** `r8s policy COMMAND [ARGS]...`

_Manages R8s policy Entity_

#### Commands

[`add`](#policy-add) Creates Policy entity.

[`delete`](#policy-delete) Deletes Policy by the provided name.

[`describe`](#policy-describe) Describes Policy entities.

[`update`](#policy-update) Updates Policy entity.


### `role`

**Usage:** `r8s role COMMAND [ARGS]...`

_Manages R8s role Entity_

#### Commands

[`add`](#role-add) Creates Role entity.

[`delete`](#role-delete) Deletes Role by the provided name.

[`describe`](#role-describe) Describes Role entities.

[`update`](#role-update) Updates Role entity.

### `user`

**Usage:** `r8s user COMMAND [ARGS]...`

_Manages R8s User entity_

#### Commands

[`delete`](#user-delete) Deletes User by the provided username.

[`describe`](#user-describe) Describes users.

[`update`](#user-update) Updates user entity.


### `algorithm`

**Usage:** `r8s algorithm  COMMAND [ARGS]...`

_Manages Algorithm Entity_

#### Commands

[`add`](#algorithm-add) Creates Algorithm entity.

[`delete`](#algorithm-delete) Deletes Algorithm entity by the provided name.

[`describe`](#algorithm-describe) Describes Algorithm entities.

[`update_general_settings`](#algorithm-update-general-settings) Updates Algorithm general settings.

[`update_clustering_settings`](#algorithm-update-clustering-settings) Updates Algorithm clustering settings.

[`update_metric_format`](#algorithm-update-metric-format) Updates Algorithm metric format settings.

[`update_recommendation_settings`](#algorithm-update-recommendation-settings) Updates Algorithm recommendation settings.


### `job`

**Usage:** `r8s job COMMAND [ARGS]...`

_Manages R8s job Entity_

#### Commands

[`submit`](#job-submit) Creates Job entity.

[`terminate`](#job-delete) Terminates Job entity by the provided by the provided job id.

[`describe`](#job-describe) Describes Job entities.



### `report`

**Usage:** `r8s report COMMAND [ARGS]...`

_Manages R8s Reports_

#### Commands

[`general`](#report-general) Creates general R8s job report.

[`download`](#report-download) Describes a R8s job report with presigned url.

[`initiate_tenant_mail_report`](#initiate-tenant-mail-report) Triggers Tenant mail report flow.

### `storage`

**Usage:** `r8s storage COMMAND [ARGS]...`

_Manages S3 Storage Entity_

#### Commands

[`add`](#storage-add) Creates Storage entity.

[`delete`](#storage-delete) Deletes Storage entity by the provided storage name.

[`describe`](#storage-describe) Describes Storage entities.

[`update`](#storage-update) Updates Storage entity.

[`describe_metrics`](#describe-metrics) Updates Storage entity.


### `application`

**Usage:** `r8s application COMMAND [ARGS]...`

_Manages Maestro RIGHTSIZER Application Entity_

#### Commands

[`add`](#application-add) Creates Application entity.

[`delete`](#application-delete) Deletes Application by the provided id.

[`describe`](#application-describe) Describes Application entities.

[`update`](#application-update) Updates Application entity.

### `application policies`

**Usage:** `r8s application policies COMMAND [ARGS]...`

_Manages Maestro RIGHTSIZER Application Group Policy Entity_

#### Commands

[`describe`](#application-policies-add) Describes Application Group Policy Entity.

[`delete`](#application-policies-delete) Deletes Application Group Policy Entity.

[`add_autoscaling`](#application-policies-add-autoscaling) Adds Application AUTO_SCALING Group Policy Entity.

[`update_autoscaling`](#application-policies-update-autoscaling) Updates Application AUTO_SCALING Group Policy Entity.

### `parent`

**Usage:** `r8s parent COMMAND [ARGS]...`

_Manages Maestro RIGHTSIZER Parent Entity_

#### Commands

[`add`](#parent-add) Creates Parent entity.

[`delete`](#parent-delete) Deletes Parent by the provided id.

[`describe`](#parent-describe) Describes Parent entities.

[`update`](#parent-update) Updates Parent entity.

[`describe_tenant_links`](#parent-describe-tenant-links) Describes Maestro tenant names linked to Parent.

[`link_tenant`](#parent-link-tenant) Links Maestro tenant to RIGHTSIZER parent.

[`unlink_tenant`](#parent-unlink-tenant) Unlinks Maestro tenant from RIGHTSIZER parent.

[`describe_resize_insights`](#describe-resize-insights) Describes resize insights for RIGHTSIZER parent and instance type.


### `shape-rule`

**Usage:** `r8s shape-rule COMMAND [ARGS]...`

_Manages Maestro Parent Shape rules_

#### Commands

[`add`](#shape-rule-add) Creates Shape Rule entity.

[`delete`](#shape-rule-delete) Deletes Shape Rule by the provided id.

[`describe`](#shape-rule-describe) Describes Shape Rule entities.

[`update`](#shape-rule-update) Updates Shape Rule entity.

[`dry_run`](#shape-dry-run) Describes shapes that satisfy all of the specified Parent rules.


### `shape`

**Usage:** `r8s shape COMMAND [ARGS]...`

_Manages R8s Shape entity_

#### Commands

[`add`](#shape-add) Creates Shape entity.

[`delete`](#shape-delete) Deletes Shape by the provided name.

[`describe`](#shape-describe) Describes Shape entities.

[`update`](#shape-update) Updates Shape entity.


### `shape price`

**Usage:** `r8s shape price COMMAND [ARGS]...`

_Manages R8s Shape Price entity_

#### Commands

[`add`](#shape-price-add) Creates Shape Price entity.

[`delete`](#shape-price-delete) Deletes Shape Price by the provided name.

[`describe`](#shape-price-describe) Describes Shape Price entities.

[`update`](#shape-price-update) Updates Shape Price entity.


### `recommendation`

**Usage:** `r8s recommendation COMMAND [ARGS]...`

_Manages R8s Recommendation entity_

#### Commands

[`describe`](#recommendation-describe) Describes Recommendation entities.

[`update`](#recommendation-update) Updates Recommendation entity.
