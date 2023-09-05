### Executor Tests

All of the test cases listed in `test_executor/` directory. 
Each test case contains part with test metric file generation.

Each metric generates separately and then converts to a pandas Dataframe with required structure.
Current options for generating dataset columns are (`utils.py`):
- Generate Timestamp series: Used to generate `timestamp` column of the dataset.
- Constant: generate column of the given length with static value. Used for 
  fields like `instance_id`, `instance_type`, `shape`, `shape_size_koef`. 
  Also `net_output_load`, `avg_disk_iops`, `max_disk_iops` 
  columns may be generated as well (for the cases where they are not 
  present at all)
- Constant with distributions: to generate values using some distribution rule: 
  refer to [NumPy docs](https://numpy.org/doc/stable/reference/random/legacy.html) 
  for available distributions
- Scheduled column value: allows to generate dataset column where its 
  values are linked to the weekday/hour. Allows to use separate 
  distributions for idle/work load. May be called several times to 
  create complex dataset columns.
  
Also, there are some options for post-processing of dataset columns (`decorators/`):
  - memory_leak: emulates memory leak (consistent growth of load with a 
    sharp drop afterwards)
  - replace: allows to randomly replace values with a new one (based on distribution)
  - move: allows shift values relatively to the timestamp
  - expand_schedule: allows shift schedule time/stop

#### Prerequisite
- Python3 installed;

#### Installation
- Navigate to `docker` directory: `cd docker/`
- Create virtual environment: `virtualenv -p python3 .venv`
- Activate virtual environment: `source .venv/bin/activate`  
- Install requirements: `python3 -m pip install -r requirements-dev.txt`
  
#### Usage:
- To discover/run all available tests: `python -m unittest discover tests_executor/`
- To be able to run specific tests separately or with IDE, add absolute 
  path to `docker` directory to `PYTHONPATH` env variable: 
  `export PYTHONPATH="$R8S_PATH/docker:$PYTHONPATH"`
- To run specific test separately: `python -m unittest tests_executor.test_constant_low_load`
- If you want to keep test results, generated metric files and their plots, remove/comment `tear_down` method from `base_executor_test.py`


