## R8s In-place metric data generation

You can replace actual instance metrics with generated datasets by specifying instance tags:
- `r8s_test_case`[REQUIRED] - defines a default config that will be used to generate 
  metric files. Without additional tags, result recommendation 
  will have the same general_action as this tag value. 
    Supported values: 
  `NO_ACTION`, `SCALE_DOWN`, `SCALE_UP`, `SHUTDOWN`, `SPLIT`, `SCHEDULE`

Common tags (Applicable for each test case):
- `r8s_period_days` - defines a time period of generated metrics file
- `r8s_cpu_load` - defines a desired average cpu load
- `r8s_memory_load` - defines a desired average memory load
- `r8s_avg_disk_iops` - defines a desired average disk iops load
- `r8s_max_disk_iops` - defines a desired max disk iops load
- `r8s_net_output_load` - defines a desired average net output load
- `r8s_std` - defines a deviation that will be used to randomize loads

`SCHEDULE` specific tags:
- `r8s_cron_start` - cron expression that handles instance starts
- `r8s_cron_stop` - cron expression that handles instance stops

`SPLIT` specific tags:
- `r8s_cpu_load` - defines a desired average cpu load *for several types of load*
- `r8s_memory_load` - defines a desired average memory load *for several types of load*
- `r8s_probability` - defines a covered percentage for each type of load

### Default configs
Default configs can be overwritten by specified instance tag. 
Note that applying tags may result in different recommendation 
action than specified in `r8s_test_case` tag

```json5
{
    "SCALE_DOWN": {
        "r8s_period_days": 14,
        "r8s_cpu_load": 20,
        "r8s_memory_load": 20,
        "r8s_avg_disk_iops": -1,
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_std": 2,
    },
    "SCALE_UP": {
        "r8s_period_days": 14,
        "r8s_cpu_load": 80,
        "r8s_memory_load": 80,
        "r8s_avg_disk_iops": -1,
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_std": 2,
    },
    "EMPTY": {
        "r8s_period_days": 14,
        "r8s_cpu_load": 45,
        "r8s_memory_load": 55,
        "r8s_avg_disk_iops": -1,
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_std": 2,
    },
    "SHUTDOWN": {
        "r8s_period_days": 14,
        "r8s_cpu_load": 5, // means load in scheduled period
        "r8s_memory_load": 3, // means load in scheduled period
        "r8s_avg_disk_iops": -1, 
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_std": 1,
    },
    "SPLIT": {
        "r8s_period_days": 14,
        "r8s_cpu_load": [25, 80], // means different load for each load types
        "r8s_memory_load": [25, 80], // means different load for each load types
        "r8s_avg_disk_iops": -1,
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_probability": [50, 50], // means % of time covered by each load
        "r8s_std": 1,
    },
    "SCHEDULE": {
        "r8s_period_days": 14,
        "r8s_cpu_load": 50,
        "r8s_memory_load": 50,
        "r8s_avg_disk_iops": -1,
        "r8s_max_disk_iops": -1,
        "r8s_net_output_load": -1,
        "r8s_std": 1,
        "r8s_cron_start": '0 9 * * 1-5',
        "r8s_cron_stop": '0 18 * * 1-5',
    },
}
```

### Examples
Most of the time, it will be enough to just set the `r8s_test_case` tag 
with the desired result action:
`NO_ACTION`, `SCALE_DOWN`, `SCALE_UP`, `SHUTDOWN`, `SPLIT`, `SCHEDULE`.

For more specific cases, see the examples below:

#### If r8s can detect a specific schedule on a specific time scale?
Tags to set:
```json5
{
  "r8s_test_case": "SCHEDULE", // for tags that are not specified, we want to use default values for SCHEDULE
  "r8s_period_days": 60, // to generate 60 days of metrics
  "r8s_cron_start": '0 12 * * 2-6',
  "r8s_cron_stop": '0 14 * * 2-6', // Instance is working from 12:00 to 14:00, Tuesday to Saturday included
}
```
!*Note that for now, only cron hours and weekdays are taken into account (hours and weekdays)*


#### If r8s can detect a split load that contains of 4 different load types?
Tags to set:
```json5
{
  "r8s_test_case": "SPLIT", // for tags that are not specified, we want to use default values for SPLIT
  "r8s_cpu_load": "25/50/70/95", 
  "r8s_memory_load": "25/50/70/95",
  "r8s_probability": "25/25/25/25", // means that each of load type (25%/50%/75%/95%) covers 25% of time
}
```
!*Note that r8s_probability values may not adds up to 100. For example, 
[10, 5, 5] probability will end up with a 50%/25%/25% probability.*

!*If overwriting default values for SPLIT case, make sure that number of periods matches for all cpu/memory/probability*

!*cpu/memory loads must be within 0-100*


#### How do we get several recommended actions in the result?
Tags to set:
```json5
{
  "r8s_test_case": "SCHEDULE", // for tags that are not specified, we want to use default values for SCHEDULE
  "r8s_cpu_load": 90, // overwriting cpu_load to force SCALE_UP
  "r8s_memory_load": 85, // overwriting memory_load to force SCALE_UP
}
```
Will result in ['SCHEDULE', 'SCALE_UP'] general actions.