import numpy as np

distribution_mapping = {
    'normal': np.random.normal,
    'binomial': np.random.binomial,
    'poisson': np.random.poisson,
    'uniform': np.random.uniform,
    'logistic': np.random.logistic,
    'multinomial': np.random.multinomial,
    'exponential': np.random.exponential,
    'chisquare': np.random.chisquare,
    'rayleigh': np.random.rayleigh,
    'pareto': np.random.pareto,
    'zipf': np.random.zipf,
}


class Distributions:
    @staticmethod
    def generate(distribution, **kwargs):
        distribution_function = distribution_mapping.get(distribution)
        if not distribution_function:
            raise KeyError(f'Invalid distribution: \'{distribution}\'')
        return distribution_function(**kwargs)
