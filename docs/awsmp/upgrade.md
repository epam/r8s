# Update Guide

The flow of product update is fully automated.

EPAM Syndicate Rightsizer implements the incremental upgrades flow - it's only
possible to update software through each successive version without skipping any intermediate versions.

Please follow the following step to update the product:

### 1. Connect to instance via SSH:
Connect to the product instance using the SSH key using this command: 
`ssh -i $SSH_KEY_NAME admin@$INSTANCE_PUBLIC_DNS` where:
   - `$SSH_KEY_NAME` is the actual name of the key file;
   - `$INSTANCE_PUBLIC_DNS` is the actual public DNS of the instance.

### 2. List releases
Once log in to instance, please execute the following command in order to list all the releases available starting from the current version:

`r8s-init list`

Here is the command output sample: 

| Version | Release Date         | URL                                                                                                | Prerelease | Draft |
|---------|----------------------|----------------------------------------------------------------------------------------------------|------------|-------|
| 3.12.0  | NEW RELEASE DATE     | [NEW RELEASE LINK](https://github.com/epam/r8s/releases/tag/3.12.0)                                | false      | false |
| 3.11.0* | 2024-01-01T09:01:13Z | [https://github.com/epam/r8s/releases/tag/3.11.0](https://github.com/epam/r8s/releases/tag/3.11.0) | false      | false |

The installed version is marked with asteriks `*` nearby the version number: `3.11.0*`.

This command is integrated with [GitHub releases of the product](https://github.com/epam/r8s/releases).

### 3. Check if update available
To check if new release is available please execute the following command:

`r8s-init update --check`

The command will return the `Up-to-date` response with the `0` status code if update is not available and `1` status code 
otherwise - this may be useful for any automation build atop of `r8s-init` tool. 

### 4. Syndicate Rightsizer Update
To initiate the update to the next version please execute the following command:

`r8s-init update --yes`

**Note:** no prompt will be shown if you specify `--yes` flag.

The command produces logs to console notifying the user about the update progress.  
> The command is fail-safe. The 'r8s-init' tool will rollback all the changes made to the software in case of failure.
> 
> This allows to return the product to the previous state. 

In case update successfully ended - the following message will be diplayed: `Done`;

### 5. Defect Dojo Update

To update Defect Dojo use:

```bash
r8s-init update --defectdojo
```

> This update is fail-safe as well.


### Support
In case of any issues please contact [SupportSyndicateTeam@epam.com](mailto:SupportSyndicateTeam@epam.com)