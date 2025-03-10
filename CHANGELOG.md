# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.11.0] - 2024-09-17
* Update onprem version of the service
* Add readable recommendation text to DefectDojo findings

## [3.10.3] - 2024-09-19
* Update DefectDojo "Product Name" naming from $Tenant_name to "RightSizer $TenantName"

## [3.10.2] - 2024-09-16
* Unify DEFECT_DOJO Application secret format with SRE

## [3.10.1] - 2024-08-30
* Add SSM secret deletion on Application force delete
* Support multiple DEFECT_DOJO application per customer

## [3.10.0] - 2024-08-16
* Implement DefectDojo integration
  * Implement API/CLI for Dojo-related Application/Parent management
  * Implement uploading RightSizer recommendation to DefectDojo

## [3.9.1] - 2024-07-24
* fix non-overwriting recommendation type while updating recent instance recommendation
* fix compatibility with latest modular_sdk 

## [3.9.0] - 2024-02-15
* extend tenant mail report content with full instance specs
* fix update algorithm timezone extraction from RIGHTSIZER_LICENSES application

## [3.8.1] - 2024-02-12
* fix invalid RecommendationHistory.resource_id references
* discard non-related resources meta from AUTOSCALING_GROUP recommendation

## [3.8.0] - 2024-02-08
* Support new Algorithm parameters:
  * max_allowed_days_schedule - Maximum allowed number of days taken for schedule processing
  * min_schedule_day_duration_minutes - Minimum allowed schedule period duration per day

## [3.7.2] - 2024-02-06
* improve handling failed group resources

## [3.7.1] - 2024-02-06
* fix `r8s license sync` response if invalid license key specified

## [3.7.0] - 2024-02-05
* implement recommendation generation for RDS instances

## [3.6.0] - 2024-02-05
* implement storing resource group recommendations in db
* implement resource group cooldown: past resource group recommendation will be reused for the period of cooldown

## [3.5.7] - 2024-02-01
* skip group resources without latest metrics available from AUTO_SCALING recommendation processing
* improve group policy threshold validation

## [3.5.6] - 2024-02-01
* r8s application policies update_autoscaling - if scale_step set to 0, AUTO_DETECT policy will be applied

## [3.5.5] - 2024-01-31
* omit SCALE_DOWN recommendation for resource group if there are less resources than proposed scale_step

## [3.5.4] - 2024-01-31
* set the "logs_expiration" parameter for lambdas

## [3.5.3] - 2024-01-26
* r8s application policies add/update_autoscaling - fix error message in case of 
  not all threshold-related parameters passed

## [3.5.2] - 2024-01-25
* Bump modular_sdk requirement to >=5.0.0,<6.0.0

## [3.5.1] - 2024-01-24
* Optimize application parents querying with Parent application_id index.

## [3.5.0] - 2024-01-24
* Implement AUTO_SCALING group policy recommendation generation
* Implement `r8s application policies` command group:
  * `describe` - Describes available group policies from application
  * `delete` - Deletes group policy from application
  * `add_autoscaling` - Configures AUTO_SCALING group policy
  * `update_autoscaling` - Updates AUTO_SCALING group policy

## [3.4.3] - 2024-01-23
* Optimize application parents querying with parent scope index.

## [3.4.2] - 2024-01-22
* fix syncing instance recommendation with RecommendationHistory item

## [3.4.1] - 2024-01-19
* fix pass allowed actions to recommendation_service.get_general_action

## [3.4.0] - 2024-01-16
* extend algorithm with `resource_type` and `allowed_actions` attributes
* Switch to LM linkage of license to algorithm by resource type
* Implement skipping recommendations of types that are not specified in algorithm `allowed_actions`

## [3.3.2] - 2024-01-10
* update modular-sdk dependency version to >=4.0.0,<5.0.0

## [3.3.1] - 2024-01-09
* update obsolete data model in mocked data generator

## [3.3.0] - 2024-01-09
* add ability to skip contradictory recommendations inside set of resources, using `r8s_group_id` tag:
  - Skip SHUTDOWN recommendations if it's not applicable for all resources in a group;
  - Skip SCALE_DOWN/SHUTDOWN recommendations if there are SCALE_UP recommendations available for some resources in group;
  - Skip custom SCHEDULE recommendations if there are resources in group with "always-run" schedule recommendations;
  - If all resources in a group have custom SCHEDULE recommendation, leave only the most common (if possible) or most complete

## [3.2.0] - 2024-01-02
* add recommended shapes probability: expected percentage of optimal load time on a new shape

## [3.1.0] - 2023-12-08
* add ability to force delete Application/Parent:
  * r8s application delete --force
  * r8s parent delete --force

## [3.0.1] - 2023-12-08
* adapt shape rules API to new Application/Parent model

## [3.0.0] - 2023-11-29
* migrate to new Application/Parent model:
  - RIGHTSIZER Application: host application
  - RIGHTSIZER Parent: links host application to tenants (ALL-scoped, auto-generated)
  - RIGHTSIZER_LICENSES Application: license application
  - RIGHTSIZER_LICENSES Parent: indicates that license is activated for tenant(s)

## [2.19.10] - 2023-11-22
* add `limit` parameter to `r8s job describe` command

## [2.19.9] - 2023-11-21
* fix non JSON serializable response in 'r8s recommendation describe' command
* hide LM tokens from logs 

## [2.19.8] - 2023-11-16
* fix tenant cloud validation on job submit
* add missing permissions for /parent/licenses endpoint
* fix duplicated recommendations for insufficient/unchanged instances
* remove raising exception if no valid metric files will be found

## [2.19.7] - 2023-11-14
* Exclude directly linked tenants (SPECIFIC/DISABLED) from ALL-scoped parent jobs
* License sync: fix set latest_sync date
* Remove obsolete permissions from admin_policy.json

## [2.19.6] - 2023-11-13
* Optimisation improvements:
  - instances with unchanged metrics (since last scan) won't be downloaded
  - recommendations will still be kept for instances with insufficient/unchanged metrics

## [2.19.5] - 2023-11-08
* Skip metrics download from s3 for instances with less daily-metric files than 
  `algorithm.recommendation_settings.min_allowed_days`

## [2.19.4] - 2023-11-06
* Fix timezone conversion while discarding metrics before instance creation
* Fix past instance recommendation querying (previously, only recommendation from current week were extracted)

## [2.19.3] - 2023-10-31
* Implement License Manager auth token storage

## [2.19.2] - 2023-10-27
* fix non-monotonic index after clustering

## [2.19.1] - 2023-10-26
* fix adapt r8s-report-generator lambda to new RecommendationHistory.savings 
  attribute format

## [2.19.0] - 2023-10-23
* Add reusage of past recommendations if no new metrics provided for instance
* Add adaptive aggregations: metrics that are older that latest point by 
  `Algorithm.optimized_aggregation_threshold_days` will be aggregated by 
  `Algorithm.optimized_aggregation_step_minutes`

## [2.18.1] - 2023-10-23
* r8s job submit: fix input_scan_tenants validation

## [2.18.0] - 2023-10-13
* Switch to new modular_sdk Parent scopes model

## [2.17.0] - 2023-10-13
* Upgrade r8s dependency versions to support python3.10

## [2.16.2] - 2023-10-10
* performance improvements:
  - add threaded s3 download
  - reformat metrics: switch from pd.iterrows to pd.apply
  - add cache to Shape get

## [2.16.1] - 2023-10-07
* Temporary update modular_sdk version in r8s_report_generator to 2.2.6a0

## [2.16.0] - 2023-10-06
* Add profiling

## [2.15.0] - 2023-09-29
* Upgrade r8s CLI dependency versions to support python 3.10

## [2.14.2] - 2023-09-06
* job submit: resolve all tenants if not specified for ALL_TENANTS scope

## [2.14.1] - 2023-09-04
* fix r8s-report-generator lambda async trigger in onprem

## [2.14.0] - 2023-08-18
* implement batch licensed jobs with independent status tracking

## [2.13.0] - 2023-08-10
* update `r8s parent shape_rule dry_run` command: add required `--cloud` parameter.
* update `r8s parent shape_rule update` command: make `--rule_id` parameter required.
* hide sensitive logs

## [2.12.5] - 2023-08-10
* fix invalid Tenant `pid` attribute extraction on job submit

## [2.12.4] - 2023-08-07
* enable RIGHTSIZER Parent shape_rules support. 

## [2.12.3] - 2023-08-07
* r8s-api-handler: hide `password`, `id_token` and `refresh_token` from logs

## [2.12.2] - 2023-08-07
* r8s cli - fix consistency of command group structure between 
  standalone/modular installation:
  - rename `shape_rule.py` to `parent_shaperule.py`, moved to `parent` subgroup
  - rename `setting_lm_client.py` to `setting_client.py`
  - rename `setting_lm_config.py` to `setting_config.py`

## [2.12.1] - 2023-08-04
* fix RIGHTSIZER parent with SPECIFIC_TENANT scope deletion 

## [2.12.0] - 2023-08-03
* License Manager integration:
  - implement RIGHTSIZER_LICENSES parent to store license-related data
  - implement `r8s parent licenses` command group

## [2.11.0] - 2023-07-25
* License Manager integration:
  - add `r8s setting config` command group, to manage License Manager access data;
  - add `r8s setting client` command group, to manage License Manager client data;
  - add `r8s license` command group, to manage r8s licences;
  - add `tenant_license_key` parameter to `r8s parent add` command. 
    On parent creation, licensed algorithm will be pulled from LM;
  - implement job permission check on submitting a job with parent 
    linked to licensed algorithm;
  - remove `r8s-job-updater` lambda, replaced with direct job state 
    updates in executor;
  - implement sending job state update requests to License Manager 
    from executor.

## [2.10.5] - 2023-07-17
* change metrics storage folder structure:
  - replace `$timestamp` with `$date` (%Y_%m_%d)
  - update `r8s job submit` cli command

## [2.10.4] - 2023-07-07
* remove mentions of `mcdm` from exported module Dockerfile

## [2.10.3] - 2023-07-06
* r8s algorithm update_recommendation_settings: change 
  `forbid_change_series` and `forbid_change_family` parameters type to bool.

## [2.10.2] - 2023-07-05
* executor: cut incomplete edge days only if there are more than two weeks of metrics

## [2.10.1] - 2023-07-04
* add missing packages in lambdas local_requirements.txt

## [2.10.0] - 2023-07-04
* implement On-Premises installation of the service
* update service diagrams

## [2.9.2] - 2023-07-03
* update shape uploading script to update setting `LAST_SHAPE_UPDATE`
* implement last shape specs/price update date: `SHAPE_UPDATE_DATE`

## [2.9.1] - 2023-07-03
* update README.md with new command description
* fix executor tests

## [2.9.0] - 2023-06-30
* update requirements.txt to install modular_sdk from pypi
* fix error with filtering shapes by metric value boundaries

## [2.8.8] - 2023-06-29
* add `r8s parent describe_resize_insights` command to describe shape selection insights

## [2.8.7] - 2023-06-29
* make instance tags for mocked metric generation case-insensitive

## [2.8.6] - 2023-06-28
* add "advanced" statistic block to instance recommendation.
* update helps in `r8s recommendation` command group

## [2.8.5] - 2023-06-27
* extend Algorithm recommendation_settings model with 
  `forbid_change_series`(bool) and `forbid_change_family`(bool) parameters

## [2.8.4] - 2023-06-27
* fix mocked data generator for gcp/azure scans

## [2.8.3] - 2023-06-26
* change `detailed` parameter type in `r8s report general` command to flag.

## [2.8.2] - 2023-06-26
* implement searching for same series/family shapes in AZURE/GCP

## [2.8.1] - 2023-06-22
* fix savings calculation for gcp scans

## [2.8.0] - 2023-06-21
* switch to modular-sdk and modular-cli-sdk
* r8s cli: fix invalid error response processing in login command

## [2.7.13] - 2023-06-20
* GOOGLE cloud support:
  - Implement script for pulling GCP shape/pricing data
  - Update executor to work with gcp shapes

## [2.7.12] - 2023-06-20
* r8s cli: fix saving invalid login response as access token

## [2.7.11] - 2023-06-16
* executor mocked data generator: change mocked metrics start date to 
  current week start instead of year start

## [2.7.10] - 2023-06-16
* executor: add check on total instance metric length after discarding.

## [2.7.9] - 2023-06-16
* r8s-report-generator: saving calculation issues fixes

## [2.7.8] - 2023-06-15
* executor:
    - add ability to discard metrics before specified creation date from instance meta
    - implement discarding metrics at the start of processing period if 
      all the metric attributes contain only zeros
* api/cli: 
  - Add `discard_initial_zeros` parameter to `r8s algorithm update_recommendation_settings`

## [2.7.7] - 2023-06-15
* r8s-report-generator: 
   - include only recommendation from latest job per resource. Max allowed 
     job age can be set in lambda env variable: `mail_report_process_days`
     Default: 7 days.
   - hide resources from priority group based on saving threshold. Min allowed
     savings amount in USD can be configured by 
     lambda env: `mail_report_high_priority_threshold`. 
     Filtering won't be applied if threshold < 0.
     Default threshold: 10$

## [2.7.6] - 2023-06-15
* r8s-report-generator: fix invalid `saving_percent` type for resources 
  with SHUTDOWN recommendation

## [2.7.5] - 2023-06-13
* Optimize `scripts/populate_azure_prices.py` script: 
    - add ability to parse specific azure regions
    - add cli arguments processing
    - divide script into two parts: updating Shape specs and Shape pricing data
* r8s-api-handler: fix 500 error on `r8s policy update` with `--attach_permission`

## [2.7.4] - 2023-06-12
* RecommendationHistory model: add `region` field
* r8s-report-generator: 
  - Add resource region;
  - Add timezone name used for instance processing; 
  - Add processing period start/stop timestamps;
  - Add `probability` coefficients for SPLIT recommendations
  - Limit number of resources in the report to 10 for each recommendation, sorted by saving desc.
* r8s-api-handler:
  - Add /reports/mail/tenant endpoint which initiates tenant report flow by async invocation of `r8s-report-generator`
* r8s cli:
  - Add `r8s report initiate_tenant_mail_report` command


## [2.7.3] - 2023-06-08
* Add ability to disable SCHEDULE recommendation type with instance meta or user adjustments

## [2.7.2] - 2023-06-07
* Unify GOOGLE/GCP cloud name to GOOGLE

## [2.7.1] - 2023-06-06
* Implement script for uploading Azure VM specs and price data to MongoDB
* Azure scan support improvements

## [2.7.0] - 2023-06-05
* Implement r8s-report-generator lambda to send Tenant reports via 3rd party application.

## [2.6.17] - 2023-06-01
* Update postpone mechanism to read from separate meta key instead of instance tags

## [2.6.16] - 2023-05-29
* Add ability to disable specific recommendation types generation with instance meta tags

## [2.6.15] - 2023-05-12
* fix invalid key names in download report response

## [2.6.14] - 2023-05-12
* r8s cli: fix broken initialization (modular mode only) for storage command group

## [2.6.13] - 2023-05-11
* `r8s storage describe_metrics` - make `tenant` parameter required, 
  optimize s3 queries, add optional `region` parameter
* Increase minimum schedule duration to 1 hour
* Increase max schedule difference for grouping to 1 hour

## [2.6.12] - 2023-05-10
* Sync with new mcdm sdk version with restricted access to modular Dynamodb tables
* Update AWS Batch compenv configuration

## [2.6.11] - 2023-05-05
* Switch to new mcdm tenant parent map updates, remove obsolete usage of tenant.save()

## [2.6.10] - 2023-05-03
* Optimize listing s3 objects in STORAGE health-check
* Hide sensitive data from logs

## [2.6.9] - 2023-05-02
* update r8s-api-handler memory (to 1024) and timeout (to 30s)
* [TEMPORARY] remove linked tenant check in parent delete

## [2.6.8] - 2023-05-02
* update `MISSING_PRICE` health-check: describe clouds with no prices available
* integrate MCDM CLI SDK
* `r8s configure`: improve error response in case of invalid api_url specified

## [2.6.7] - 2023-04-28
* Update r8s CLI Readme
* Implement Configuration compatibility check
* Improve Suspicious prices check: detect suspicious prices based on shape price-per-cpu

## [2.6.6] - 2023-04-26
* Fix overwriting recent recommendation in RecommendationHistory collection
* Handle exception with unknown timezone specified in algorithm

## [2.6.5] - 2023-04-25
* Rework `r8s health-check` command
* [Temporary] Disable filtering metric files by RIGHTSIZER parent scope
* Replace `--application_id` in r8s shape_rule describe with `--rule_id`
* Fix error on `r8s shape_rule` update with invalid rule_id passed  
* Forbid to link tenant to parent if their clouds differ
* Add ability to overwrite tag name for instance postpone by r8s-api-handler 
  env variable `META_POSTPONED_KEY`

## [2.6.4] - 2023-04-21
* Implement `r8s shape_rule dry_run` command

## [2.6.3] - 2023-04-18
* Implement metrics file filtering by parent scope
* Implement commands for link/unlink tenants to/from parent, describe linked tenants

## [2.6.2] - 2023-04-04
* Implement API handler/cli command for health-check

## [2.6.1] - 2023-03-31
* Implement Shape/Shape Price API and cli commands
* Implement User API for user registration and management

## [2.6.0] - 2023-03-29
* Implement separate storage for Shape and Shape Price
* Replace Model with Algorithm:
  - Remove obsolete ml model usage
  - Extend Algorithm model with parameters that can influence scan workflow
  - Implement Algorithm API/cli commands
* Remove Job Definition Entity (replaced with modular Application/Parent meta)
* Modular Application:
  - Implement API/cli commands for management
  - Extend meta with `connection`, `input_storage` and `output_storage` attributes
* Modular Parent:
  - Implement API/cli commands for management
  - Extend meta with:
    1) cloud - define allowed cloud to scan
    2) scope - define allowed tenants
    3) algorithm - define r8s algorithm which will be used in scans
    4) shape rules - define list of rules for applying limitations to 
       instance types that will be available for recommendation
* Job Submit API/ cli command: now accepts `parent_id` (required) and 
  `application_id` (optional) parameters to resolve Parent/Application that 
  will be used in scan       

## [2.5.0] - 2023-03-07
* Add separation of metrics and results by cloud
* r8s cli: add "scan_clouds" parameter to r8s job submit
* r8s cli: add `cloud`, 'instance_id' and `detailed` parameters to `r8s report general` command
* r8s cli: remove obsolete `r8s report resize` command
* r8s cli: implement `user describe`, `user update` and `user delete` commands

## [2.4.0] - 2023-02-27
* Implement saving calculations for instance recommendations

## [2.3.2] - 2023-02-22
* Fix invalid `general_action` type in error response (str instead of list)
* Skip the last day of metrics if it's incomplete
* Improve error handling: return error result on unexpected exceptions

## [2.3.1] - 2023-02-06
* Fix executor tests to work with clustering
* Improve error handling: save instance result even if its metric file is not valid
* Changed default schedule for mocked data to Mon-Fri instead of Tue-Sat

## [2.3.0] - 2023-02-03
* Implement metrics clustering

## [2.2.1] - 2023-01-24
* Pull meta from `meta_info.json` file instead of separate file per instance.

## [2.2.0] - 2023-01-18
* Implement in-place test metrics generation, configurable by instance meta

## [2.1.0] - 2023-01-16
* Rename `prob` in schedule recommendation to `probability`
* Rename `general_action` to `general_actions`, return list of recommendation 
  actions instead of single one

## [2.0.2] - 2023-01-13
* Fix API unit tests


## [2.0.1] - 2023-01-05
* Implement merging metrics if several files for single instance found.
* Implement `r8s storage describe_metrics` to describe available instances 
  and their timestamps
* Check if all required settings are set on job submit 
* r8s: Fix incorrect command helps
* r8s: Add human-readable response for errors instead of traceback in case of unexpected response.


## [2.0.0] - 2022-12-15
* Improve schedule recommendation algorithm: 
  - Recommended schedules are now weekly-based
  - Recommended schedules covers all non-idle load on the instance
  - Recommended schedule probability is calculated based on ML-model result.
  - Similar schedules for different days can be grouped with work period extension
  - Requires at least 14 days of collected instance telemetry
* Improve shape recommendation algorithm:   
  - Suitable shapes searched in a way that current instance load on a new 
    instance type to fall within reasonable 30-70%
  - Suitable shapes searched in the next order: prioritized shapes, same series shapes, same family_type_shapes, other
* Implement ability to pass instance meta into algorithm;
* Implement customer shapes preferences
* Implement test data generator
* Implement executor tests

## [1.0.3] - 2022-11-01
* Make `--password` parameter in `r8s login` secured

## [1.0.2] - 2022-11-01
* Reload credentials on each call in order to use updated credentials when 
  running under the m3modular server

## [1.0.1] - 2022-10-31
* Fix compatibility of r8s cli with m3modular

## [1.0.0] - 2022-08-30
* Initial release of RightSizer Service.

