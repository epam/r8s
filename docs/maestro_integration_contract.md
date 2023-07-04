# Maestro-R8s Integration contract

## Prerequisites

- R8s deployed on same AWS account with Maestro
- R8s configured:
    * Model Created
    * Storage Created
    * Data Source Created
    * Job Definition Created
    * User for Maestro created
    
- BE team provided with:
    * Storage bucket name/prefix
    * Data source bucket name/prefix (bucket name may be same for metrics and results storing)
    * Job definition name
    * R8s host url
    * Maestro user credentials

## Storage formats

### Metrics format

All metrics for processing must be stored in target job definition data source
with next structure:

`$DATA_SOURCE_PREFIX/$CUSTOMER_NAME/$TENANT_NAME/$REGION_NAME/$TIMESTAMP/$INSTANCE_ID.csv`

Where:

- $DATA_SOURCE_PREFIX - metrics prefix (if any)
- $CUSTOMER_NAME - Maestro Customer name (ex. "EPAM Systems")
- $TENANT_NAME - Maestro Tenant name (ex. AWS-MSTR-DEV2)
- $REGION_NAME - Native cloud region name (ex. eu-central-1)
- $TIMESTAMP - timestamp (ex. 1666951200000)
- $INSTANCE_ID.csv - instance metric file

### Results format

All job results will be stored in target job definition storage with next
structure:
`$STORAGE_PREFIX/$JOB_ID/$TENANT_NAME/$REGION_NAME/$TIMESTAMP.jsonl`

Where:

- $STORAGE_PREFIX - results prefix (if any)
- $JOB_ID - job id, can be extracted from Submit job request
- $TENANT_NAME - Maestro Tenant name (ex. AWS-MSTR-DEV2)
- $REGION_NAME - Native cloud region name (ex. eu-central-1)
- TIMESTAMP.jsonl - Stores all job results for the given Customer/Tenant/Region
  instances (item per line)

## Scan flow

1. Login 
   Request URL: $HOST/r8s/signin  
   METHOD: POST BODY:

    ```json
    {
      "username": "$USERNAME",
      "password": "$PASSWORD"
    }
    ```

`id_token` from response must be set in `Authorization` header for the next
calls

2. Submit job 
   Request URL: $HOST/r8s/jobs HTTP Method: POST
   Headers: `{"Authorization": "$TOKEN_FROM_LOGIN_REQUEST"}`
   Body:

    ```json
    {
      "job_definition": "$JOB_DEFINITION_NAME",
      "customer": "$CUSTOMER_NAME",
      "tenants": ["$TENANT_NAME1", "$TENANT_NAME2"],
      "scan_timestamp": "$SCAN_TIMESTAMP"
    }
    ```

    Save `job_id` from response to track status/extract recommendations

3. Get job status
   Request URL: $HOST/r8s/jobs 
   HTTP Method: GET
   Headers: `{"Authorization": "$TOKEN_FROM_LOGIN_REQUEST"}`
   Query:

    ```json
    {
      "id": "$JOB_ID"
    }
    ```
If job status is "SUCCEEDED", recommendations can be found in Storage 
S3 bucket under `$STORAGE_PREFIX/$JOB_ID/` prefix