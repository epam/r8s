import numpy as np

from tests_executor.distributions import Distributions


def replace(series, probability, distribution, **kwargs):
    """
    Replace value in given series with given probability to new value generated
    by specified distribution

    :param series: series to randomly replcae value in
    :param probability: probability of replacement (for single item)
    :param distribution: distribution used to generate new value
    :param kwargs: parameters required by distribution function
    :return:
    """
    for index, value in enumerate(series):
        rand = np.random.random()

        if rand < probability:
            value = Distributions.generate(
                distribution=distribution,
                **kwargs)
            if value < 0:
                value = 0
            series[index] = value
    return series
