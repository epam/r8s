### Vault Installation & Configuration on Windows

### Installation:
#### Using Chocolatey:
Open Terminal as Administrator and run the following command:
```powershell
PS> choco install vault
```
>If you don't have Choco installed, see the installation guide at the end of this file.

#### To verify the installation:
```powershell
PS> vault
```
> ❗ If you get an error that the binary could not be found, then 
> your PATH 
environment variable was not setup properly. Please go back and ensure that your PATH variable contains the directory where Vault was installed.

#### Set `VAULT_TOKEN` environment variable:
```powershell
PS> setx VAULT_TOKEN {YOUR_SECRET_TOKEN}
```

#### To run the dev vault server use:
```powershell
PS> vault server -dev -dev-root-token-id="$Env:VAULT_TOKEN"
```
> ❗ "VAULT_TOKEN" will be used to have access to vault


On production environment you may want to use production-ready configuration 
instead of development server. Production configuration guide for Unix systems is [here](Prod_configuration.md).


#### Choco installation
```powershell
PS> Set-ExecutionPolicy Bypass -Scope Process -Force; `
  iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
```

> Next step: Install + configure MinIO: [Windows](../MinIO/Windows.md)