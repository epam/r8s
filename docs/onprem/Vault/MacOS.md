## Vault Installation & Configuration on MacOS

### Installation:

1. Install the HashiCorp tap, a repository of all our Homebrew packages:
    ```
    brew tap hashicorp/tap
    ```

2. Install Vault with `hashicorp/tap/vault`:
    ```
    brew install hashicorp/tap/vault
    ```
3. To update to the latest, run:
    ```
    brew upgrade hashicorp/tap/vault
    ```
   
4. After installing Vault, verify the installation worked by opening a 
   new terminal session and checking that the vault binary is available. 
   By executing `vault`, you should see help output similar to the following:
    ```
    $ vault
    
    Usage: vault <command> [args]
    
    Common commands:
        read        Read data and retrieves secrets
        write       Write data, configuration, and secrets
        delete      Delete secrets and configuration
        list        List data or secrets
        login       Authenticate locally
        agent       Start a Vault agent
        server      Start a Vault server
        status      Print seal and HA status
        unwrap      Unwrap a wrapped secret
    
    Other commands:
        audit          Interact with audit devices
        auth           Interact with auth methods
        debug          Runs the debug command
        kv             Interact with Vault's Key-Value storage
        lease          Interact with leases
        monitor        Stream log messages from a Vault server
        namespace      Interact with namespaces
        operator       Perform operator-specific tasks
        path-help      Retrieve API help for paths
        plugin         Interact with Vault plugins and catalog
        policy         Interact with policies
        print          Prints runtime configurations
        secrets        Interact with secrets engines
        ssh            Initiate an SSH session
        token          Interact with tokens
    ```
   
### Configuration:

On production environment you may want to use production-ready configuration 
instead of development server. Production configuration guide is [here](Prod_configuration.md)

- Export the `VAULT_TOKEN` environment variable which will be used to get 
access to VAULT storage:

  ```bash
  $ export VAULT_TOKEN={YOUR_SECRET_TOKEN}
  ```

- Start the development server:

  ```bash
  $ vault server -dev -dev-root-token-id=$VAULT_TOKEN
  ```

   
> Next step: Install + configure MinIO: [MacOS](../MinIO/MacOS.md)