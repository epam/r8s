# Introduction

Syndicate RightSizer is an AI-empowered offering that reviews the existing virtual instances in terms of their
configuration, workload, and lifecycle, and produces the following types of recommendations, all accompanied by expected
cost savings/raise:

- Resize (scale up or scale down) instance – change the instance type within the current family
- Split – split a single instance workload into several instances, each facing a specific workload type for it.
- Schedule – create start/stop schedules for the instance to be cost effective without affecting its capacity.
- Shut down – terminate the instance due to the low to no load.

The recommendations are built based on up to 60 days of instances performance history, and are delivered as .JSON files.

The solution API can be used for effective convenient integrations and additional visualization.

## Table of Contents

1. [Introduction](#introduction)
2. [EPAM Syndicate RightSizer Deployment](#epam-syndicate-rightsizer-deployment)
    - [Pre-Requisites](#pre-requisites)
    - [Required Permissions](#required-permissions)
    - [Components Overview](#components-overview)
    - [Deployed Environment Configuration and Resources](#deployed-environment-configuration-and-resources)
3. [EPAM Syndicate RightSizer Configuration](#epam-syndicate-rightsizer-configuration)
    - [Initial AMI Instance Launch](#initial-ami-instance-launch)
    - [Initializing AMI for another Linux User](#initializing-ami-for-another-linux-user)
    - [User Registration](#user-registration)
    - [Activating Tenants](#activating-tenants)
    - [License Management](#license-management)
4. [Product Maintenance and Support](#product-maintenance-and-support)
    - [Product Health Check](#product-health-check)
    - [Product Troubleshooting](#product-troubleshooting)
    - [Backup And Recovery](#backup-and-recovery)
    - [Upgrades and Patches](#upgrades-and-patches)
5. [Security Highlights](#security-highlights)
    - [Rotating Keys And Credentials](#rotating-keys-and-credentials)
    - [Policies and Privileges](#policies-and-privileges)
    - [Data Encryption](#data-encryption)
6. [Scanning and Reporting](#scanning-and-reporting)
    - [Quick Start](#quick-start)
    - [Requesting Scan with specific License](#requesting-scan-with-specific-license)
    - [Requesting Scan for specific Tenant](#requesting-scan-for-specific-tenant)
7. [Support](#support)
8. [Annexes](#annexes)
    - [Annex 1: Secrets Inside AMI](#annex-1-secrets-inside-ami)
    - [Annex 2: Permissions](#annex-2-permissions)
    - [Annex 3: License Pricing](#annex-3-license-pricing)

{{ pagebreak }}

## Use Case Examples

Below, you can find a list of real-life use cases for the product that illustrate the range of its possibilities:

### FinOps Optimization

**Problem Statement:**  
An enterprise needs to make the FinOps processes more effective and transparent.

**Solution:**  
Activating FinOps checks to see virtual machines expenses trends.

**Result:**  
Improved transparency, reaction and estimation of the FinOps processes.

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# EPAM Syndicate RightSizer Deployment

The product is deployed as an AMI provisioned on:

- [EPAM Solutions Hub](https://solutionshub.epam.com/solution/epam-syndicate-rightsizer)
- [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-w5euwv2axwy32)

Once you obtain the AMI, you need to launch an instance from it and start the product.

> **Note:** The deployment with AMI and necessary post-configuration typically takes up to 30 minutes.

## Pre-Requisites

The deployment pre-requisites include technical and skill-based ones.

### Technical Pre-Requisites

- Having an AWS account
- Having permissions enough to run new EC2 instances

> **Note:** No other deployment prerequisites are to be met, as the offering is delivered via an AMI.

### User Skills Requirements

To set up EPAM Syndicate RightSizer and work with it effectively, you need to:

- Have basic EC2 knowledge -- to run an AWS AMI image
- Have Unix/Linux command line knowledge -- to run the configuration script

## Required Permissions

EPAM Syndicate RightSizer requires several IAM permissions to access ec2 configuration / metric statistic.
The necessary permissions are listed below:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

{{ pagebreak }}

## Components Overview

The Architecture diagram below provides the view on the main components of the offering, provisioned within the AMI.

### Reference Diagram

![Reference Diagram](./r8s_arch_context.png)

*Figure 1 - Reference Diagram*

### Containers Diagram using AMI on EC2

![Containers Diagram using AMI on EC2](./r8s_arch.png)

*Figure 2 - Containers Diagram*

{{ pagebreak }}

## Deployed Environment Configuration and Resources

During the product deployment, a set of AWS and System resources are created.

### AWS Resources

The AMI-based deployment relies on an instance with the following minimum configuration:

- **OS:** Ubuntu (Canonical, Ubuntu, 22.04 LTS, amd64 jammy image)
- **vCPU:** 2
- **RAM:** 8 GB
- **Disk:** 30 GB, at least GP3 3000 IOPS

> **Note:** The provisioned AMI is available across all AWS regions. These parameters can be used for estimating cost of
> the solution in a specific deployment region.

### System Resources

During the deployment, several secrets are generated. They all belong to the Linux user with ID 1000 and are stored in
the `/usr/local/r8s/secrets/` directory. No one else has read permission to this folder.

### Customer Sensitive Data

- Customer's secrets if they exist are stored inside Vault. Vault has a docker volume attached.
- Customer's scans results data is stored inside Minio bucket `r8s-reports`.

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# EPAM Syndicate RightSizer Configuration

After an instance with the EPAM Syndicate RightSizer is deployed from the provisioned AMI, several steps are to be made
to complete the configuration:

- [Initial AMI Instance Launch](#initial-ami-instance-launch) -- the basic login and S.RightSizer start
- [Initializing AMI for another Linux User](#initializing-ami-for-another-linux-user) -- enabling the S.RightSizer for a
  new Linux user
- [User Registration](#user-registration) -- registering a new user to enable S.RightSizer performance
- [License Management](#license-management) -- managing licenses

## Initial AMI Instance Launch

When AMI is launched and its instance status check is green, you can log in to the instance via SSH and use EPAM
Syndicate RightSizer immediately from the syndicate CLI entry point.

There are two groups of commands:

- **`syndicate r8s ...`** -- used to access scanning and reporting API (*r8s* stands for "RightSizer")
- **`syndicate admin ...`** -- used to manage logical entities that represent accounts and organizations (admin -
  entities administrator)

## Initializing AMI for another Linux User

The AMI has a script called **`r8s-init`** that allows you to initialize EPAM Syndicate RightSizer for a new Linux user.
By default, only the first non-root Linux user has RightSizer installed.

If you want to initialize the S.RightSizer for other Linux users, execute the command:

```console
r8s-init --user "username" --public-ssh-key "ssh-..." --r8s-username job_submitter --r8s-password $SECRET_PASSWORD
```

A user with name **username** will be created if it does not exist yet. If **`--public-ssh-key`** is specified, it will
be added to `~/.ssh/authorized_keys` of that user. You can also provide **`--r8s-username`** & **`--r8s-password`** of
an S.RightSizer user created before to set these credentials.

## User Registration

A user is needed for the EPAM Syndicate RightSizer to perform. Before creating one, it is necessary to create a separate
policy and role for them.

### Steps

**1. Create a policy:**

```console
syndicate r8s policy add --policy_name "demo_policy" --permission "r8s:job:describe_job" --permission "r8s:job:describe_report"
```

> **Note:** The list of all permissions can be found in [Annex 2: Permissions](#annex-2-permissions).

**2. Create a role:**

```console
r8s role add --name demo_role --policies demo_policy --expiration "2026-01-01T00:00:00"
```

**3. Create a user:**

```console
syndicate r8s register --username demo_user --password $SECRET_PASSWORD --customer_id $CUSTOMER --role_name "demo_role"
```

**4. Log in as the newly created user** or give its credentials to someone else:

```console
syndicate r8s login --username demo_user --password $SECRET_PASSWORD
syndicate r8s job describe
```

### Managing Permission, Policies and Roles

**Permissions can be added and removed** from policy with the following command:

```console
syndicate r8s policy update --policy_name "demo_policy" --attach_permission "r8s:health_check:describe_health_check" --detach_permission "r8s:job:describe_report"
```

**Policies can be added and removed** from roles with the following command:

```console
r8s role update --name demo_role --attach_policy "some_other_policy" --detach_policy "demo_policy"
```

## Activating Tenants

A tenant is a main entity that EPAM Syndicate RightSizer manages and requires. One tenant represents one AWS Account.

When an instance is launched from AMI, one tenant is created automatically. Its default name is `CURRENT_ACCOUNT` and it
represents the AWS account where the AMI was launched. This tenant has one active region (the one where instance is
launched). In case the instance profile allowed READ access to the AWS account, that tenant can be immediately used.

### Creating API Users

When the AMI is launched, Admin users are created for the EPAM Syndicate RightSizer and for the Modular Service. They
are configured by default. Their passwords are placed to:

- `/usr/local/r8s/secrets/rightsizer-pass`
- `/usr/local/r8s/secrets/modular-service-pass`

> **Note:** All the sensitive information is listed in [Annex 1: Secrets Inside AMI](#annex-1-secrets-inside-ami).
> Username **`customer_admin`** is default for both and can be configured via User data script before instance startup.

Your admin S.RightSizer user has rights to manage other users inside your customer:

```console
syndicate r8s user describe
```

Each user has an assigned role. Each role can have multiple policies attached. Each policy can allow specific actions
over API, so you can flexibly configure access to the system.

## License Management

A license is a logical entity that issues analysis algorithms for scanning.

Each customer can have a license assigned to it and therefore a unique set of algorithms. Licenses are issued by EPAM
Syndicate License Manager.

Each AMI-based instance will have a single license. You can add more licenses to the installation if you have license
keys. Those can be issued by the Syndicate License Manager team.

### Adding a License

Let's assume you have a license key and want to add it to the installation.

**1. Add a license:**

```console
syndicate r8s application licenses add --customer_id $CUSTOMER_ID --description "Newly added license" --cloud $CLOUD --tenant_license_key $LICENSE_KEY
```

**2. Activate the license for tenants.** You must do that because you can have overlap (two different licenses can issue
different algorithms for the same tenant):

```console
syndicate r8s parent add --application_id $APPLICATION_ID --description "New License activation for tenant" --tenant $TENANT

```

Alternatively, you can just allow license to be used by all available tenants:

```console
syndicate r8s parent add --application_id $APPLICATION_ID --description "New License activation for tenant" --scope ALL
```

> **Note:** License Key from the previous command is not the same as `$TENANT_LICENSE_KEY`.
> **Note:** Application Id parameter used in the commands above obtained as a result of executing
`syndicate r8s application licenses add` command.

To prolong, update, or cancel an existing license, please contact the support team.

> **Tip:** The overview of available plans and prices are given in [Annex 3: License Pricing](#annex-3-license-pricing).

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# Product Maintenance and Support

EPAM Syndicate RightSizer includes a set of tools, checks and services that enable effective maintenance and support:

- [Product Health Check](#product-health-check) -- the check of the main components status
- [Product Troubleshooting](#product-troubleshooting) -- the fixes for the typical possible issues
- [Backup and Recovery](#backup-and-recovery) -- the recommendations on the backup and recovery approaches
- [Upgrades and Patches](#upgrades-and-patches) -- the processes of the product updates and patches deployment

## Product Health Check

EPAM Syndicate RightSizer has its health check. It makes sure that:

- Minio is available
- Mongo is available
- Vault is available
- Necessary buckets exist in Minio
- License Manager private key is configured
- License Manager API link is configured
- System customer setting configured
- S.RightSizer secret key exists in Vault
- Availability of cloud instance types
- Availability of VM metrics

To perform the health check procedure, run:

```console
syndicate r8s health_check
```

## Product Troubleshooting

The health check procedure can return several statuses that need your attention.

### Status: NOT_OK

**Action:** Contact the support team.

### Status: Job has finished with status FAILED

**Action:** Describe the job using the command below and look at the `reason` field.

```console
syndicate r8s job describe --job_id $JOB_ID
```

The `reason` can be one of these:

#### License manager does not allow this job

Your license has expired or the limit of jobs is exceeded or license manager is temporarily unavailable. Try to submit
the job again in a while and if it does not help - contact the support team.

#### Internal executor error

The executor failed with internal reason. Contact the support team.

### Status: Cannot submit job

If the `syndicate r8s job submit` command returns:

#### Affected license has expired

Your license has expired.

#### Tenant could not be granted to start a licensed job

Our license manager does not allow submitting the license. Either your jobs limit per period was exceeded or LM is
temporarily unavailable. Try again in a while.

#### Remaining job balance X is greater than requested number of tenants: Y

You're trying to perform analysis on a bigger number of tenants than allowed by your license remaining balance. Try
submitting the job with smaller amount of tenants.

### Status: Cannot execute any command because token has expired

If `syndicate ...` any command returns **"The provided token has expired. Please re-login to get a new token"**, try the
following:

```console
syndicate login
```

## Backup And Recovery

The main backup strategy for the product is using an AMI Snapshot. You can either use the initial AMI provisioned for
the product deployment, or create a custom snapshot using standard AWS tools.

For tenant data export, it is recommended to arrange backup to an external storage.

Also, you can export docker volumes:

- `vault-data`
- `mongo-data`
- `minio-data`
- `defectdojo_data`
- `defectdojo_postgres`
- `defectdojo_media`
- `defectdojo_redis`

## Upgrades and Patches

The upgrades and patches for the product are delivered within updated AMIs and changes on GitHub.

The components upgrade and patches application logic is in-built into the solution. To initiate components update and
data patching, you need to authenticate to the host instance using SSH and admin user and execute the following command:

```console
r8s-init
```

> **Note:** The update can take from several minutes up to one hour, depending on the amount of changes and data. The
> process needs service downtime.

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# Security Highlights

EPAM Syndicate RightSizer security includes the following keystone approaches:

- [Rotating Keys And Credentials](#rotating-keys-and-credentials)
- [Policies and Privileges](#policies-and-privileges)
- [Data Encryption](#data-encryption)

Below, the details on each part are given.

## Rotating Keys And Credentials

The following tools and approaches are applied for keys rotation within the solution:

### Rotate your S.RightSizer user's password

```console
syndicate r8s user update --username $USERNAME --password $NEW_PASSWORD
syndicate r8s login --username $USERNAME --password $NEW_PASSWORD
```

### Rotate your Modular Service user's password

```console
syndicate admin users change_password --password $NEW_PASSWORD
syndicate admin login --username $USERNAME --password $NEW_PASSWORD
```

### Rotate your Modular API password (experimental, only for `sudo` user)

```console
sudo docker exec modular-api python modular.py user change_password --username $MODULAR_API_USER --password $NEW_PASSWORD
syndicate setup --username $MODULAR_API_USER --password $NEW_PASSWORD --api_path http://127.0.0.1:8085 # re-login
```

### Automatically Generated Keys

**The keys for the following components are automatically generated** at the service start, and stored on the OS level,
preserving the security of the OS users access:

- Vault, Mongo, Minio credentials
- Defect Dojo credentials and secret keys
- S.RightSizer Secret keys

## Policies and Privileges

The following approaches for policies and privileges on your AWS account are highly recommended to ensure the
infrastructure security:

- The product does not need AWS root account privileges
- Do not use AWS account root user for any deployment or operations
- The principle of least privilege is an option of choice when it comes to access granted within the deployment
- There are no public resources except the License Manager.
- Instance metadata V2 is used during setup to retrieve instance identity document and its signature

## Data Encryption

EPAM Syndicate RightSizer follows these encryption approaches:

- All communication between docker containers is NOT encrypted (http)
- Communication with the License Manager is encrypted
- There is no persistent encryption for Minio and Mongo
- Vault is sealed when the instance is stopped and unsealed when it's started

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# Scanning and Reporting

The main tool for EPAM Syndicate RightSizer usage is the CLI.

Further in this section, you can find the instructions on specific actions that can be performed with the tool:

- [Quick Start](#quick-start) -- basic steps to perform your first scans
- [Requesting Scan with specific License](#requesting-scan-with-specific-license) -- requesting a scan with a specific
  License available within S.RightSizer
- [Requesting Scan for specific Tenant](#requesting-scan-for-specific-tenant) -- requesting a scan for specific Tenant(
  s)

## Quick Start

When the AMI instance is running, you **can log in using SSH and immediately use EPAM Syndicate RightSizer**.

```console
ssh -i "private-key.pem" admin@domain.compute.amazonaws.com
syndicate version
```

**Syndicate** is the main CLI entry point that you should use to interact with S.RightSizer API and Modular Service API.
S.RightSizer API allows you to execute scans and receive reports. Modular Service is an admin API. It allows you to
configure such organization entities as Customers and Tenants. Use commands `syndicate r8s` and `syndicate admin`
accordingly.

### Authentication

Both S.RightSizer API and Modular Service API have authentication mechanisms and credentials to access them. Those were
set for you during setup and their refresh tokens are updated automatically when the session ends. The syndicate tool
also has its authentication mechanism, and it may require you to log in once in a while.

If any **syndicate ... command tells that the session has ended, use this command**:

```console
syndicate login
```

> **Note:** Credentials are stored here: `~/.modular_cli/`

### Available Entities and Resources

From the beginning, the only entity that represents the AWS account where the instance is running is activated.
Such entities are called Tenants.

**Describe tenants** using this command:

```console
syndicate admin tenant describe
```

> **Note:** This one by default has `CURRENT_ACCOUNT` name that must be used to reference this entity.

When the instance was starting, it made a request to our License Manager and received a license.

**Describe the license** using this command:

```console
syndicate r8s application licenses describe
```

**Describe available analysis algorithms**:

```console
syndicate r8s algorithm describe
```

### Executing Scans

If the instance has an Instance Role with access to this AWS Account, Syndicate RightSizer will start to aggregate VM
metrics to ite internal storage.
Once that is done, you can request analysis with command:

```console
syndicate r8s job submit
```

S.RightSizer will use algorithms that are available by license.
With default configuration (1 Cloud Account, 1 License) no additional parameters needed.

**To see the job status**, use:

```console
syndicate r8s job describe --job_id $JOB_ID --json
```

> **Note:** Job id used in the request is obtained in the response of `syndicate r8s job submit` command

### Retrieving Reports

When the status is `SUCCEEDED`, you can **request some reports**:

```console
syndicate r8s recommendation describe --job_id "$JOB_ID" --json
```

## Requesting Scan with specific License

In case your configuration contains several active licenses, you'll need to specify the exact one.
Firstly, you'll need to list your licenses to pick the right one.

```console
syndicate r8s application licenses describe --json
```

Secondly, you'll need to pass correct `application_id` into the `submit` command:

```console
syndicate r8s job submit --application_id $application_id --json
```

## Requesting Scan for specific Tenant

In case your configuration contains several Tenants, you may want to analyze only specific ones:

```console
syndicate r8s job submit --scan_tenants $TENANT1 --scan_tenants $TENANT2 --json
```

### DefectDojo Integration

When the AMI-based instance is running, you can access **Defect Dojo UI** on port 8080 of the instance public IPv4. The
Admin password is inside the `/usr/local/r8s/secrets/defect-dojo-pass` file. Admin username is `admin`. S.RightSizer is
configured to push results of each job automatically, so you should see active findings after at least one job was
successfully finished.

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# Support

EPAM Syndicate RightSizer support team is available by <SupportSyndicateTeam@epam.com> email.

Please address all your questions and we will respond within 3 business days (Ukraine schedule).

## Professional Service Offering

Within the Professional Service offering, the customer gets a dedicated expert, who:

- Assists with performing analysis using the S.RightSizer tool
- Performs tool configuration by customer's request
- Performs as the Tech Support entry point
- Suggests Syndicate toolset expansion, based on the declared customer needs

### Tool Information

- **Company:** EPAM
- **Tool:** EPAM Syndicate RightSizer
- **Support Contact:** SupportSyndicateTeam@epam.com
- **Response Time:** Within 3 business days (Ukraine schedule)

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

# Annexes

## Annex 1: Secrets Inside AMI

All the secrets that are generated during installation belong to the Linux user with id 1000. They are inside
`/usr/local/r8s/secrets/`. There are these files:

| **File**               | **Description**                                                                                                                                                                                     |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `defect-dojo-pass`     | Defect Dojo admin password                                                                                                                                                                          |
| `modular-service-pass` | Modular service admin user password                                                                                                                                                                 |
| `rightsizer-pass`      | S.RightSizer admin user password                                                                                                                                                                    |
| `rightsizer.env`       | S.RightSizer environment variables generated before starting the server. It contains credentials to microservices (mongo, minio and vault) and system password for S.RightSizer and Modular Service |
| `defect-dojo.env`      | Defect Dojo environment variables generated before starting the server                                                                                                                              |
| `lm-link`              | Syndicate License Manager API link                                                                                                                                                                  |
| `lm-response`          | Syndicate License Manager API response. It contains tenant license key and private keys to sign requests                                                                                            |

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

## Annex 2: Permissions

Permission model is aligned with the API available for managing the system. This API includes the following groups:

- [Diagnostics](#diagnostics)
- [Credentials management & user authorization](#credentials-management--user-authorization)
- [Management and license information API](#management-and-license-information-api)
- [API necessary for DefectDojo integration](#api-necessary-for-defectdojo-integration)
- [Customisation-oriented API methods](#customisation-oriented-api-methods)

### Diagnostics

| **Endpoint**                      | **Permission**                             | **Description**                               |
|-----------------------------------|--------------------------------------------|-----------------------------------------------|
| POST /health-check                | r8s:health_check:describe_health_check     | Performs system health checks                 |
| POST /jobs/                       | r8s:job:submit_job                         | Allows to submit job                          |
| GET /jobs                         | r8s:job:describe_job                       | Allows to query jobs                          |
| DELETE /jobs                      | r8s:job:terminate_job                      | Allows to terminate a job that is running     |
| POST /refresh                     | -                                          | Allows to refresh the access token            |
| GET /storages/data/               | r8s:storage:describe_metrics               | Allows to describe metrics available for scan |
| GET /recommendations/             | r8s:recommendation:describe_recommendation | Allows to describe recommendation             |
| GET /parents/shape-rules/dry-run/ | r8s:parent:dry_run_shape_rule              | Allows to perform dry run for shape rule      |
| GET /reports/                     | r8s:job:describe_report                    | Allows to describe report                     |

{{ pagebreak }}

### Credentials management & user authorization

| **Endpoint**      | **Permission**               | **Description**                                     |
|-------------------|------------------------------|-----------------------------------------------------|
| POST /signup      | -                            | Registers a new API user                            |
| POST /signin      | -                            | Allows log in and receive access and refresh tokens |
| POST /policies    | r8s:iam:create_policy        | Allows to create a policy                           |
| POST /roles       | r8s:iam:create_role          | Allows to create a role                             |
| GET /policies     | r8s:iam:describe_policy      | Allows to describe policies                         |
| GET /roles        | iam:describe_role            | Allows to describe roles                            |
| DELETE /policies/ | r8s:iam:remove_policy        | Allows to delete a policy by name                   |
| DELETE /roles/    | r8s:iam:remove_role          | Allows to delete a role by name                     |
| PATCH /policies/  | r8s:iam:update_policy        | Allows to update a policy by name                   |
| PATCH /roles/     | r8s:iam:update_role          | Allows to update a role by name                     |
| DELETE /users/    | r8s:iam:delete_user          | Allows to delete a specific user                    |
| GET /users        | r8s:iam:describe_user        | Allows to get an API user by name                   |
| PATCH /users/     | r8s:iam:update_user_password | Allows to update a specific user's password         |

{{ pagebreak }}

### Management and license information API

| **Endpoint**                            | **Permission**                       | **Description**                                              |
|-----------------------------------------|--------------------------------------|--------------------------------------------------------------|
| GET /applications                       | r8s:application:describe_application | Allows to list Applications of "RIGHTSIZER" type             |
| POST /applications                      | r8s:application:create_application   | Allows to create Application of "RIGHTSIZER" type            |
| PATCH /applications                     | r8s:application:update_application   | Allows to update Application of "RIGHTSIZER" type            |
| DELETE /applications                    | r8s:application:remove_application   | Allows to delete Application of "RIGHTSIZER" type            |
| GET /applications/licenses/             | r8s:application:describe_application | Allows to describe application of "RIGHTSIZER_LICENSES" type |
| POST /applications/licenses/            | r8s:application:create_application   | Allows to create application of "RIGHTSIZER_LICENSES" type   |
| PATCH /applications/licenses/           | r8s:application:update_application   | Allows to update application of "RIGHTSIZER_LICENSES" type   |
| DELETE /applications/licenses/          | r8s:application:remove_application   | Allows to remove application of "RIGHTSIZER_LICENSES" type   |
| GET /algorithms/                        | r8s:algorithm:describe_algorithm     | Allows to describe analysis algorithm                        |
| DELETE /algorithms/                     | r8s:algorithm:remove_algorithm       | Allows to remove analysis algorithm                          |
| GET /storages/                          | r8s:storage:describe_storage         | Allows to describe storage                                   |
| POST /storages/                         | r8s:storage:create_storage           | Allows to create storage                                     |
| PATCH /storages/                        | r8s:storage:update_storage           | Allows to update storage                                     |
| DELETE /storages/                       | r8s:storage:remove_storage           | Allows to remove storage                                     |
| GET /parents/                           | r8s:parent:describe_parent           | Allows to describe parent                                    |
| POST /parents/                          | r8s:parent:create_parent             | Allows to create parent                                      |
| PATCH /parents/                         | r8s:parent:update_parent             | Allows to update parent                                      |
| DELETE /parents/                        | r8s:parent:remove_parent             | Allows to remove parent                                      |
| GET /shapes/                            | r8s:shape:describe_shape             | Allows to describe shape                                     |
| POST /shapes/                           | r8s:shape:create_shape               | Allows to create shape                                       |
| PATCH /shapes/                          | r8s:shape:update_shape               | Allows to update shape                                       |
| DELETE /shapes/                         | r8s:shape:remove_shape               | Allows to remove shape                                       |
| GET /shapes/prices/                     | r8s:shape:describe_shape_price       | Allows to describe shape price                               |
| POST /shapes/prices/                    | r8s:shape:create_shape_price         | Allows to create shape price                                 |
| PATCH /shapes/prices/                   | r8s:shape:update_shape_price         | Allows to update shape price                                 |
| DELETE /shapes/prices/                  | r8s:shape:remove_shape_price         | Allows to remove shape price                                 |
| GET /licenses/                          | r8s:license:describe_license         | Allows to describe license                                   |
| DELETE /licenses/                       | r8s:license:delete_license           | Allows to delete license                                     |
| POST /licenses/sync/                    | r8s:license:sync_license             | Allows to sync license                                       |
| GET /settings/license-manager/config    | r8s:setting:describe_lm_config       | Allows to describe License Manager config                    |
| POST /settings/license-manager/config   | r8s:setting:create_lm_config         | Allows to create License Manager config                      |
| DELETE /settings/license-manager/config | r8s:setting:delete_lm_config         | Allows to delete License Manager config                      |
| GET /settings/license-manager/client    | r8s:setting:describe_lm_client       | Allows to describe License Manager client                    |
| POST /settings/license-manager/client   | r8s:setting:create_lm_client         | Allows to create License Manager client                      |
| DELETE /settings/license-manager/client | r8s:setting:delete_lm_client         | Allows to delete License Manager client                      |

{{ pagebreak }}

### API necessary for DefectDojo integration

| **Endpoint**               | **Permission**                            | **Description**                     |
|----------------------------|-------------------------------------------|-------------------------------------|
| GET /applications/dojo/    | r8s:application:describe_dojo_application | Allows to describe dojo application |
| POST /applications/dojo/   | r8s:application:create_dojo_application   | Allows to create dojo application   |
| PATCH /applications/dojo/  | r8s:application:update_dojo_application   | Allows to update dojo application   |
| DELETE /applications/dojo/ | r8s:application:remove_dojo_application   | Allows to remove dojo application   |
| GET /parents/dojo/         | r8s:parent:describe_dojo_parent           | Allows to describe dojo parent      |
| POST /parents/dojo/        | r8s:parent:create_dojo_parent             | Allows to create dojo parent        |
| PATCH /parents/dojo/       | r8s:parent:update_dojo_parent             | Allows to update dojo parent        |
| DELETE /parents/dojo/      | r8s:parent:remove_dojo_parent             | Allows to remove dojo parent        |

{{ pagebreak }}

### Customisation-oriented API methods

| **Endpoint**                     | **Permission**                           | **Description**                           |
|----------------------------------|------------------------------------------|-------------------------------------------|
| GET /parents/shape-rules/        | r8s:parent:describe_shape_rule           | Allows to describe shape rule             |
| POST /parents/shape-rules/       | r8s:parent:create_shape_rule             | Allows to create shape rule               |
| PATCH /parents/shape-rules/      | r8s:parent:update_shape_rule             | Allows to update shape rule               |
| DELETE /parents/shape-rules/     | r8s:parent:remove_shape_rule             | Allows to remove shape rule               |
| GET /parents/resource-groups/    | r8s:parent:describe_group_config         | Allows to describe group config           |
| POST /parents/resource-groups/   | r8s:parent:add_group_config              | Allows to add group config                |
| PATCH /parents/resource-groups/  | r8s:parent:update_group_config           | Allows to update group config             |
| DELETE /parents/resource-groups/ | r8s:parent:delete_group_config           | Allows to delete group config             |
| PATCH /recommendations/          | r8s:recommendation:update_recommendation | Allows to provide recommendation feedback |

[Go to Table of Contents](#table-of-contents)

{{ pagebreak }}

## Annex 3: License Pricing

### To rewrite, content is taken from SRE guide

EPAM Syndicate Rule Engine product is licensed according to the following pricing:

- **Open Source** -- Allows deploying the service on your own and enable security compliance for free using the demo
  license that includes 60 rules (20 per AWS, Azure, GCP clouds each)

- **Basic Security** -- Best match for Startups who do not have a dedicated Security Expert. Receive regularly updated
  full set of rules, up to 3 Well-Architected and FinOps reviews monthly

- **Standard Security** -- Option to have a reliable security support of the software. Receive regularly updated full
  set of rules, up to 10 Well-Architected and FinOps reviews monthly

- **Zero Tolerance Security** -- Minimize possible losses related to data leaks and infrastructure backdoors of your
  critical software components. Receive regularly updated full set of rules, and unlimited Well-Architected and FinOps
  reviews

The set of provisioned services and additional features depends on the selected option. Each next level can be
considered as an expansion of the previous one.

### Plans Comparison

| **Features**                           | **Open Source Free**               | **Basic Security $3,000/mon**                  | **Standard Security $6,400/mon**               | **Zero Tolerance Security $14,000/mon**        |
|----------------------------------------|------------------------------------|------------------------------------------------|------------------------------------------------|------------------------------------------------|
| **Professional service hours**         | 0                                  | 24                                             | 64                                             | 160                                            |
| **Minimum commitment month**           | -                                  | 3                                              | 3                                              | 3                                              |
| **Rules Available**                    | Demo Pack (60 rules, 20 per cloud) | All rules available (1150+), regularly updated | All rules available (1150+), regularly updated | All rules available (1150+), regularly updated |
| **DefectDojo integration**             | +                                  | +                                              | +                                              | +                                              |
| **Well-Architected review**            | -                                  | up to 3 accounts                               | up to 10 accounts                              | unlimited                                      |
| **FinOps assessment**                  | -                                  | up to 3 accounts                               | up to 10 accounts                              | unlimited                                      |
| **Monthly updates**                    | -                                  | +                                              | +                                              | +                                              |
| **Service introduction call (45 min)** | -                                  | +                                              | +                                              | +                                              |

{{ pagebreak }}

### Detailed Plan Descriptions (SKU)

| **PLAN NAME (SKU)**               | **DESCRIPTION**                                                                                                                                                                              |
|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Open Source (SRE_FREE)            | Allows deploying the service on your own and enable security compliance for free. No professional hours, no minimum commitment. Free.                                                        |
| Basic Security (SRE_BASIC)        | Best match for Startups who do not have a dedicated Security Expert, 24 professional service hours, 3 minimum commitment months, $3000/month*                                                |
| Standard Security (SRE_SMB)       | Option to have a reliable security support of the software. 64 professional service hours, 3 minimum commitment months, $6400/month*                                                         |
| Zero Tolerance Security (SRE_ENT) | Minimize possible losses related to data leaks and infrastructure backdoors of your critical software components. 160 professional service hours, 3 minimum commitment months, $14000/month* |

> **Note:** *The price is given in USD, taxes not included, the list price, may be changed. You can check for the
> updates on the product [EPAM Solutions Hub page](https://solutionshub.epam.com/solution/syndicate-rule-engine).
