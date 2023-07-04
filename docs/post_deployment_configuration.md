### Maestro RightSizer Post Deployment Configuration


#### Environment / system admin user configuration

1. Execute environment configuration script:
   `python3 scripts/configure_environment.py --access_key $AWS_ACCESS_KEY \
   --secret_key $AWS_SECRET_ACCESS_KEY \
   --session_token $AWS_SESSION_TOKEN \
   --region $AWS_REGION \
   --r8s_mongodb_connection_uri $MONGODB_CONNECTION_URI/r8s \
   --cognito_user_pool_name r8s`
1.1. Save returned admin username and password
   
2. Populate Shape/Shape Pricing collection with initial data:
   `python3 scripts/populate_aws_shapes.py \
   --access_key $AWS_ACCESS_KEY \
   --secret_key $AWS_SECRET_ACCESS_KEY \
   --session_token $AWS_SESSION_TOKEN \
   --region AWS_REGION \
   --r8s_mongodb_connection_uri $CONNECTION_URI/r8s \
   --price_region eu-central-1 --price_region eu-west-1 \
   --operating_system Windows --operating_system Linux`

#### r8s cli configuration

3. Install r8s cli: 
   `python3 -m pip install $PATH_TO/r8s/r8s`

4. Configure r8s cli:
    `r8s configure --api_link https://$API_ID.execute-api.{REGION}.amazonaws.com/r8s`
   
5. Login using the credentials from step 1
    `r8s login --username $USERNAME --password $PASSWORD`
   
#### R8s recommendation engine configuration   

6. Create Input storage (data source)
   `r8s storage add --storage_name maestro_input_storage \
   --type DATA_SOURCE \
   --bucket_name $BUCKET_NAME \
   --prefix "metrics"`

7. Create Output storage
   `r8s storage add \
   --storage_name maestro_output_storage \
   --type STORAGE \
   --bucket_name $BUCKET_NAME \
   --prefix "results"`

8. Create algorithm 
   `r8s algorithm add --algorithm_name maestro_algorithm \
   --customer "EPAM Systems" --cloud AWS -da instance_id -da instance_type \
   -da timestamp -da cpu_load  -da memory_load -da net_output_load \
   -da avg_disk_iops -da max_disk_iops -ma cpu_load -ma memory_load \
   -ma net_output_load -ma avg_disk_iops \ -ta timestamp`

9. Set algorithm recommendation settings:
   `r8s algorithm update_recommendation_settings \
   --algorithm_name maestro_algorithm \
   --record_step_minutes 10 \
   --threshold 10 --threshold 30 --threshold 70\
   --min_allowed_days 1 \
   --max_days 90 \
   --min_allowed_days_schedule 14\
   --shape_compatibility_rule NONE \
   --shape_sorting PRICE`

#### Maestro Entities configuration

10. Create policy For Maestro:
   `r8s policy add --policy_name maestro_policy \
    --path_to_permissions $PATH/r8s/scripts/admin_policy.json`

11. Create role For Maestro:
   `r8s role add --name maestro_role \
   --policies maestro_policy --expiration 2024-01-01T00:00:00`
    
12. Create user For Maestro:
   `r8s register --username maestro_user \
    --password "$PASSWORD" --customer "EPAM Systems" \
    --role_name maestro_role`

13. Create RIGHTSIZER Application
   `r8s application add \
   --customer "EPAM Systems" \
   --description "Maestro Rightsizer Application" \ 
   --input_storage maestro_input_storage \
   --output_storage maestro_output_storage \
   --username $MAESTRO_USERNAME \
   --password $MAESTRO_PASSWORD`

14. Create RIGHTSIZER Parent
    `r8s parent add --application_id $APPLICATION_ID \ 
    --description "Rightsizer Parent" \
    --cloud AWS \
    --algorithm maestro_algorithm \
    --scope ALL_TENANTS`
   
#### Verification
15. Execute health-check report:
`r8s health-check --json`
    
16. Review returned report:
    - `applications` key: ensure that created application exists and passed all checks
    - `parents` key: ensure that created parent exists and passed all checks
    - `storages` key: ensure that created storages exist. Ensure that input 
      storage has some valid metric files ("instances" list is not empty)
    - `operation_mode_result`: Ensure that there's at least one 
      completely-filled object, meaning that jobs can be submitted 
      using that application/parent pair
    - `shapes` key: Ensure that there are Shapes/Prices for at least one 
      cloud/region, not the suspicious prices and found shapes without prices
      
17. Submit r8s job: 
    `r8s job submit --application_id $APPLICATION_ID --parent_id $PARANT_ID`
    
18. Ensure tha job finish successfully, review job report