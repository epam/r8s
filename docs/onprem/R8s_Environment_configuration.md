### CaaS Environment Configuration

#### Prerequisites:
1. Installed & Configured [MinIO](MinIO/), [Vault](Vault/) and [MongoDB](MongoDB/)
2. Configured [syndicate_aliases.yml](Configure_Aliases.md)
3. Installed Python [components](Install_Python_Components.md)
4. Installed, Configured and logged in [r8s](Configure_r8s.md)
5. AWS/AZURE Shape data/price uploaded using the [populate_aws_shapes.py](../../scripts/populate_aws_shapes.py) and [populate_azure_shapes.py](../../scripts/populate_azure_shapes.py) scripts

#### Environment Configuration:   
1. Export env variables from syndicate_aliases.yml
2. Export desired customer name to `CUSTOMER_NAME` env var.
3. Run the server with python3 src/main.py.
On the first run, r8s will create some entities:
    - admin role, policy and user: credentials will be printed to the console.
    - Maestro Customer with name, specified in env var.
    - Vault token that will be used in encryption
    
4. Configure r8s cli with `r8s configure --api_link $API_LINK`
5. Login using the system admin credentials provided: `r8s login --username SYSTEM_ADMIN --password $PASWORD`
6. Create storages: 
    - Input storage (Metric source): `r8s storage add --storage_name input_storage --type DATA_SOURCE --bucket_name r8s-storage --prefix metrics`
    - Output (Results destination): `r8s storage add --storage_name output_storage --type STORAGE --bucket_name r8s-storage --prefix results`
    
7. Create algorithm for AWS:
  ```shell
   r8s algorithm --algorithm_name maestro_algorithm \
     --customer_id $CUSTOMER_ID \
     --cloud AWS \
     --timestamp_attribute timestamp
   ```
8. Create Rightsizer application: 
   ```shell
   r8s application add --customer_id $CUSTOMER_ID \
     --description "RightSizer Application" --input_storage input_storage \
     --output_storage output_storage --username SYSTEM_ADMIN \
     --password $PASSWORD --host $API_HOST \
     --port $API_PORT --protocol HTTP"
   ```
9. Create Rightsizer parent (AWS): `r8s parent add --application_id $AID --description "RIGHTSIZER Parent for AWS" --cloud AWS --scope ALL_TENANTS`
10. Upload instance metrics to `r8s-metrics` bucket, following the folder structure: 
    `r8s-metrics/metrics/$CUSTOMER/$CLOUD/$TENANT/$REGION/$TIMESTAMP/$INSTANCE_ID.csv`
11. Submit job: 
   ```shell
   r8s job submit --parent_id $PARENT_ID --customer_id $CUSTOMER_ID
   ```
