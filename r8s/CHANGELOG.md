# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.15.0] - 2023-09-29
* Upgrade r8s CLI dependency versions to support python 3.10

## [2.12.2] - 2023-08-07
* r8s cli - fix consistency of command group structure between 
  standalone/modular installation:
  - rename `shape_rule.py` to `parent_shaperule.py`, moved to `parent` subgroup
  - rename `setting_lm_client.py` to `setting_client.py`
  - rename `setting_lm_config.py` to `setting_config.py`
* hide sensitive logs

## [2.11.0] - 2023-07-25
* License Manager integration:
  - add `r8s setting config` command group, to manage License Manager access data;
  - add `r8s setting client` command group, to manage License Manager client data;
  - add `r8s license` command group, to manage r8s licences;
  - add `tenant_license_key` parameter to `r8s parent add` command.

## [2.10.5] - 2023-07-17
* `r8s job submit` commend:
  - remove `--scan_timestamp` parameter
  - add `--scan_date_from` and `scan_date_to` parameters

## [2.10.3] - 2023-07-06
* r8s algorithm update_recommendation_settings: change 
  `forbid_change_series` and `forbid_change_family` parameters type to bool.

## [2.6.9] - 2023-05-24
* Fix an issue when invalid values passed for `r8s login` command [EPMCEOOS-4912]

## [2.6.8] - 2023-05-02
* integrate MCDM CLI SDK
* `r8s configure`: improve error response in case of invalid api_url specified

## [2.6.0] - 2023-03-29
* Implement separate storage for Shape and Shape Price
* Replace Model with Algorithm:
  - Remove obsolete ml model usage
  - Extend Algorithm model with parameters that can influence scan workflow
  - Implement Algorithm API/cli commands
* Remove Job Definition Entity (replaced with Maestro Application/Parent meta)
* Maestro Application:
  - Implement API/cli commands for management
  - Extend meta with `connection`, `input_storage` and `output_storage` attributes
* Maestro Parent:
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
* r8s cli: add "scan_clouds" parameter to r8s job submit
* r8s cli: add `cloud`, 'instance_id' and `detailed` parameters to `r8s report general` command
* r8s cli: remove obsolete `r8s report resize` command
* r8s cli: implement `user describe`, 'user update' and `user delete` commands

## [2.0.1] - 2023-01-05
* Implement `r8s storage describe_metrics` to describe available instances 
  and their timestamps
* Fix incorrect command helps
* Add human-readable response for errors instead of traceback in case of unexpected response.

## [1.0.3] - 2022-11-01
* Make `--password` parameter in `r8s login` secured

## [1.0.2] - 2022-11-01
* Reload credentials on each call in order to use updated credentials when 
  running under the m3modular server

## [1.0.1] - 2022-10-31
* Fix compatibility of r8s cli with m3modular

## [1.0.0] - 2022-08-30
* Initial release of Maestro RightSizer Service.

