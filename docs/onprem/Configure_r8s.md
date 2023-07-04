### **Install `r8s` - CLI tool:**

In order to perform versatile operations with RightSizer entities and manage the system you have to install `r8s` package by the path `r8s/r8s`.

**Create and activate a separate virtual environment:**

```bash
python -m venv r8s_venv
. ./r8s_venv/bin/activate  # Linux/Mac
r8s_venv\Scripts\activate  # Windows
```

**Install CLI tool:**

```bash
(r8s_venv) pip install ./r8s
```

*Note*: make sure you are going to install exact the package within this repository of custodian-as-a-service (r8s folder), but not the one from PyPI. 

To check whether the tool is installed correctly, execute `r8s` from the created earlier virtual environment. You should see help message like this:

```bash
(r8s_venv) r8s
Usage: r8s [OPTIONS] COMMAND [ARGS]...

  The main click's group to accumulates all the CLI commands

Options:
  -v, --version  Show the version and exit.
  --help         Show this message and exit.

Commands:
  algorithm       Manages Algorithm Entity
  application     Manages RIGHTSIZER Application Entity
  cleanup         Removes all the configuration data related to the tool.
  configure       Configures r8s tool to work with r8s API.
  health-check    Describes a R8s health check status.
  job             Manages job Entity
  login           Authenticates user to work with R8s.
  parent          Manages RIGHTSIZER Parent Entity
  policy          Manages Policy Entity
  recommendation  Manages Recommendation Entity
  register        Creates user to work with R8s.
  report          Manages reports
  role            Manages Role Entity
  shape           Manages Shape Entity
  shape_rule      Manages Shape rule Entity
  storage         Manages storage entity
  user            Manages User Entity
```