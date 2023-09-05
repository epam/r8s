## Python components installation

### Installing r8s

**Clone the [repository](https://git.epam.com/epmc-eoos/r8s) with r8s:**

**Switch to `feature/onprem` branch**


*Note:* make sure you have GIT installed and configured on your local machine and ample rights to access this repository.

**Move the appeared folder**:

```bash
cd r8s
```

**Create Python virtual environment `venv` and activate it. You must have Python and Pip installed:**

Create environment:
```bash
python -m venv venv
```
Activation for Linux/Mac:
```bash
. ./venv/bin/activate
```
Activation for Windows:
```powershell
venv\Scripts\activate
```

> ❗ All the next interactions and installations must be performed under `venv`.

**Install lambdas' requirements:**

On Linux/Mac (Bash):

```bash
for d in src/lambdas/*; do if [ -d "$d" ]; then pip install -r "$d/requirements.txt"; fi; done
```

On Windows (PowerShell):

```powershell
foreach ($d in Get-ChildItem .\src\lambdas\){if ( $d.PSIsContainer) {pip install -r ${pwd}\src\lambdas\$d\requirements.txt}}
```

Also nobody is going to punish you if you want to install all the lambdas' requirements manually. Just repeat the following command for each lambda:

```bash 
pip install -r src/lambdas/{lambda_name}/requirements.txt
```

**Install other necessary requirements:**

* The requirements for docker:

  ```bash
  pip install -r docker/requirements.txt
  ```
* The requirements for components inside `scripts/` folder:

  ```bash
  pip install -r scripts/requirements.txt
  ```
* The requirements for the main application. Depending on the way you want to 
  execute R8s you have to install a little different requirements. 
  If you need to run the remote version - install `src/requirements.txt`, 
  in case you need to run it locally - install `src/exported_module/requirements.txt`:
  ```bash
  pip install -r src/requirements.txt  # remotely
  ```
  ```bash
  pip install -r src/exported_module/requirements.txt  # locally
  ```