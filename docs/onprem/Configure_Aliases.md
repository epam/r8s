## Syndicate aliases description

### Overview

When a user executes the main API `app.py`, all the key-values from 
`syndicate.yml` and `syndicate_aliases.yml`  is parsed and set to environment. 
They will be available like env variables all the time while API is working. 
So, before executing the main script, you should specify all the necessary 
key-value pairs inside `syndicate_aliases.yml` to make the it work properly.


### syndicate.yml
1. Create `syndicate_configs` folder for syndicate config files inside R8S
   root folder.
2. Inside `syndicate_configs` folder, create file with name `syndicate.yml` and 
   add following variables into it:
```yaml
project_path: /$PATH_TO_R8S_ROOT/r8s
resources_prefix: <suffix> 
resources_suffix: <prefix>
```
Where:
- `project_path` - absolute path to R8s root folder
- `resources_prefix` - resources prefix. Leave it as is
- `resources_suffix` - resources prefix. Leave it as is

### syndicate_aliases.yml
1. Inside of `syndicate_configs` folder, create file called 
   `syndicate_aliases.yml` and 
   add following variables into it:
```yaml
region: eu-central-1
log_level: DEBUG
DEBUG: True

SERVICE_MODE: docker # r8s mode. Leave it by default.
MONGO_DATABASE: r8s # Name of MongoDB database to use. Leave it by default to disable.
MONGO_USER: mongouser1 # Your mongo user username
MONGO_PASSWORD: mongopassword # your mongo server user password
MONGO_URL: 127.0.0.1:27017 # your mongo server host:port
VAULT_URL: 127.0.0.1 # Your Vault server host
VAULT_SERVICE_SERVICE_PORT: 8200 # Your Vault server port
VAULT_TOKEN: vaulttoken # Your Vault dev root token
MINIO_ACCESS_KEY: access_key # you MinIO user access key
MINIO_SECRET_ACCESS_KEY: secret_access_key # you MinIO secret access key
MINIO_HOST: 127.0.0.1 # Your MinIO server host
MINIO_PORT: 41149 # Your MinIO server port
EXECUTOR_PATH: $PATH/r8s/docker/executor.py # Absolute path to executor.py
VENV_PATH: /$PATH/r8s/venv/bin/python3.8 # Absolute path to virtualenv python executable
logs_expiration: 30 # The expiration period of Lambda's CloudWatch logs in days
```   

*Keep in mind:* likely you won't be ready to put some secret keys or tokens 
inside `syndicate_aliases.yml` file for reasons of security. 
Nonetheless you have to set all the necessary variables at least to 
global OS environment.

#### MinIO:

- **MINIO_ACCESS_KEY**: must contain the valid access key (name) of a 
  particular user which is already added to MinIO;
- **MINIO_SECRET_ACCESS_KEY**: it goes together with MinIO access key 
  and must be specified in order to have access to the storage server;
- **MINIO_HOST**: the host, where MinIO server is running. Likely, 
  it is `127.0.0.1` (localhost), but you must set exactly the one, 
  your server uses;
- **MINIO_PORT**: the port, the server is running on.

#### Vault:

* **VAULT_URL**: the host, where Vault server is running;
* **VAULT_SERVICE_SERVICE_PORT**: the port, Vault service binds;
* **VAULT_TOKEN**: the secret token, Vault requires to access its secrets.

#### MongoDB:
* **MONGO_DATABASE**: the name of the main system's database;
* **MONGO_USER**: the name of the user, which has rights to manage the database above;
* **MONGO_PASSWORD**: the user's password;
* **MONGO_URL**: the host and the port where MongoDB is currently running. Must be split by colon (localhost:27017).
