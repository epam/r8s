def move(series, delta_points, reverse=False):
    if reverse:
        series = series[::-1]

    delta_series = series[0:delta_points]
    series = series[delta_points:] + delta_series

    if reverse:
        return series[::-1]
    return series
