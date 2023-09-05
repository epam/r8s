### License Manager Configuration

#### Prerequisites:
- Installed & configured `r8s` cli
- Installed & configured `cslm` cli


##### Configuration consists of two parts:
1. License Manager side:
   - Registration of LM service client
   - Generation of service client keys
   - Creation of licensed r8s algorithms
   - License creation
   - License activation for specific customer/client type
2. Rightsizer side:
   - LM access data configuration (Must be provided by CSLM support team)
   - LM client key configuration (Must be provided by CSLM support team)
   - License activation

#### License Manager side:
1. Registration of LM service client:  
    `cslm client add --client_type SAAS --customer $CUSTOMER --permit True`
   
    Save `client_id` from response for further use.

2. Generation of service client keys:  
    `cslm client km rotate --client_id $CLIENT_ID
                            --key_type ECC 
                            --key_standard p521     
                            --hash_type SHA 
                            --hash_standard 256 
                            --sig_scheme DSS 
                            --format PEM --json `

3. Creation of licensed r8s algorithms:  
    `cslm algorithm add --name LM_AWS_DEFAULT --algorithm_id DEFAULT_AWS --cloud AWS --description "DEFAULT Licensed Algorithm" --target_timezone_name UTC`

4. License creation:  
    `cslm license add --service_type RIGHTSIZER --algorithm_id DEFAULT_AWS --valid_until 2024-01-01T00:00:00 --job_balance 10 --time_range DAY --independent`

5. License activation for specific customer/client type:  
    `cslm license assign --license_key $LICENSE_KEY --customer $CUSTOMER --allowed_client_types SAAS --permit`

For further configuration on client (r8s) side, next items should be collected:
- License Manager access data: `HOST`, `PORT`, `STAGE` and `PROTOCOL` - common for all clients;
- License Manager client key: `key_id`, `algorithm`, `format`, `private_key` - from step 2;
- Tenant license key: from step 5.

#### RightSizer side:

1. LM access data configuration:  
    `r8s setting config add --host $HOST --port $PORT --stage $STAGE --protocol $PROTOCOL`
   
2. LM client key configuration:  
    `r8s setting client add --key_id $KEY_ID --algorithm $ALGORITHM --format $FORMAT --b64encoded --private_key $PRIVATE_KEY`
   
3. License activation:  
    `r8s parent add --application_id $APPLICATION_ID --description $DESCRIPTION --cloud AWS --tenant_license_key $TENANT_LICENSE_KEY --scope ALL_TENANTS`
   
4. Verify licensed algorithm created:  
    `r8s algorithm describe --algorithm_name DEFAULT_AWS`
   
5. Submit job using licensed parent:  
    `r8s job submit --parent_id $PARENT_ID --scan_tenants $TENANT_NAME`
   
6. Verify job status  
    `r8s job submit --job-id $JOB_ID`
   