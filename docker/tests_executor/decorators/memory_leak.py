import numpy as np


def memory_leak(series, mean, limit, cycle_duration_points, deviation):
    current_cycle_step = 0
    step = (limit - mean) / cycle_duration_points
    for index, value in enumerate(series):
        if current_cycle_step < cycle_duration_points:
            new_value = value + (current_cycle_step * step)
            new_value = np.random.normal(loc=new_value, scale=deviation)
            if new_value > 100:
                new_value = 100
            series[index] = new_value
            current_cycle_step += 1
        else:
            current_cycle_step = 0
    return series
