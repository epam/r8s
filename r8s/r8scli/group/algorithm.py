import click

from r8scli.group import cli_response, ViewCommand, cast_to_list
from r8scli.service.constants import AVAILABLE_CLOUDS, AVAILABLE_QUOTING, \
    AVAILABLE_KMEANS_INIT, AVAILABLE_KNEE_INTERP_OPTIONS, \
    AVAILABLE_SHAPE_COMPATIBILITY_RULES, AVAILABLE_SHAPE_SORTING, \
    AVAILABLE_ANALYSIS_PRICE
from r8scli.service.local_response_processor import LocalCommandResponse

QUOTING_HELP = """Controls when quotes should be recognised by the reader.

QUOTE_ALL - quote all fields
QUOTE_MINIMAL[default] - only quote those fields which contain special 
characters such as delimiter, quotechar or any of the characters 
in lineterminator
QUOTE_NONNUMERIC - quote all non-numeric fields
QUOTE_NONE - never quote fields
"""

DEFAULT_DATA_ATTRIBUTES = [
    "instance_id",
    "instance_type",
    "timestamp",
    "cpu_load",
    "memory_load",
    "net_output_load",
    "avg_disk_iops",
    "max_disk_iops"
]
DEFAULT_METRIC_ATTRIBUTES = [
    "cpu_load",
    "memory_load",
    "net_output_load",
    "avg_disk_iops"
]

parameter_not_specified = lambda v: bool(v) if isinstance(v, list) \
    else v is not None


@click.group(name='algorithm')
def algorithm():
    """Manages Algorithm Entity"""


@algorithm.command(cls=ViewCommand, name='describe')
@click.option('--algorithm_name', '-name', type=str,
              help='Algorithm name to describe.')
@cli_response()
def describe(algorithm_name=None):
    """
    Describes a R8s algorithm.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().algorithm_get(algorithm_name=algorithm_name)


@algorithm.command(cls=ViewCommand, name='add')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to create.')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Algorithm customer.')
@click.option('--cloud', '-c',
              type=click.Choice(AVAILABLE_CLOUDS),
              required=True, help='Algorithm cloud.')
@click.option('--data_attribute', '-da', multiple=True,
              required=False,
              help=f'List of required data attributes for the algorithm. '
                   f'Default: {DEFAULT_DATA_ATTRIBUTES}')
@click.option('--metric_attribute', '-ma', multiple=True,
              required=False,
              help=f'List of metric attributes for the algorithm. '
                   f'Default: {DEFAULT_METRIC_ATTRIBUTES}')
@click.option('--timestamp_attribute', '-ta', type=str, required=True,
              help='Name of the column that will be used as timestamp.')
@cli_response()
def add(algorithm_name, customer_id, cloud, data_attribute,
        metric_attribute, timestamp_attribute):
    """
    Creates a R8s Algorithm.
    """
    from r8scli.service.initializer import init_configuration

    data_attributes = cast_to_list(data_attribute)
    if not data_attributes:
        data_attributes = DEFAULT_DATA_ATTRIBUTES

    metric_attributes = cast_to_list(metric_attribute)
    if not metric_attributes:
        metric_attributes = DEFAULT_METRIC_ATTRIBUTES

    return init_configuration().algorithm_post(
        algorithm_name=algorithm_name,
        customer=customer_id,
        cloud=cloud,
        data_attributes=data_attributes,
        metric_attributes=metric_attributes,
        timestamp_attribute=timestamp_attribute
    )


@algorithm.command(cls=ViewCommand, name='update_general_settings')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to update.')
@click.option('--data_attribute', '-da', multiple=True,
              required=False,
              help='List of required data attributes for the algorithm')
@click.option('--metric_attribute', '-ma', multiple=True,
              required=False,
              help='List of metric attributes for the algorithm')
@click.option('--timestamp_attribute', '-ta', type=str, required=False,
              help='Name of the column that will be used as timestamp.')
@cli_response()
def update_general_settings(algorithm_name, data_attribute, metric_attribute,
                         timestamp_attribute):
    """
    Updates a R8s algorithm general settings.
    """
    from r8scli.service.initializer import init_configuration

    data_attribute = cast_to_list(data_attribute)
    metric_attribute = cast_to_list(metric_attribute)

    optional_parameters = (data_attribute, metric_attribute, timestamp_attribute)
    if not any(parameter_not_specified(param) for param
               in optional_parameters):
        response = {'message': "At least one of the optional "
                               "parameters must be specified"}
        return LocalCommandResponse(body=response)

    return init_configuration().algorithm_pathc_general_settings(
        algorithm_name=algorithm_name,
        data_attribute=data_attribute,
        metric_attribute=metric_attribute,
        timestamp_attribute=timestamp_attribute
    )


@algorithm.command(cls=ViewCommand, name='update_metric_format')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to update.')
@click.option('--delimiter', '-d', type=str, required=False,
              help='A one-character string used to separate fields. '
                   'Max lengh: 2 chars')
@click.option('--skipinitialspace', '-sis', type=bool, required=False,
              help='When True, spaces immediately following the delimiter '
                   'are ignored.')
@click.option('--lineterminator', '-ln', type=str, required=False,
              help='The string used to terminate lines. Defaults to "\r\n". '
                   'Max lengh: 3 chars')
@click.option('--quotechar', '-qch', type=str, required=False,
              help='A one-character string used to quote '
                   'fields containing special characters')
@click.option('--quoting', '-q',
              type=click.Choice(list(AVAILABLE_QUOTING.keys())),
              help=f'{QUOTING_HELP}')
@click.option('--escapechar', '-ech', type=str, required=False,
              help='A one-character string used to escape the delimiter '
                   'if quoting is set to QUOTE_NONE and the quotechar '
                   'if doublequote is False')
@click.option('--doublequote', '-dq', type=bool, required=False,
              help='Controls how instances of quotechar appearing inside '
                   'a field should themselves be quoted. When True, the '
                   'character is doubled. When False, the escapechar is '
                   'used as a prefix to the quotechar. It defaults to True.')
@cli_response()
def update_metric_format(algorithm_name, delimiter, skipinitialspace,
                         lineterminator, quotechar, quoting, escapechar,
                         doublequote):
    """
    Updates a R8s algorithm metric format settings.
    """
    from r8scli.service.initializer import init_configuration

    optional_parameters = (delimiter, skipinitialspace, lineterminator,
                           quotechar, quoting, escapechar, doublequote)
    if not any(parameter_not_specified(param) for param
               in optional_parameters):
        response = {'message': "At least one of the optional "
                               "parameters must be specified"}
        return LocalCommandResponse(body=response)

    return init_configuration().algorithm_patch_metric_format(
        algorithm_name=algorithm_name,
        delimiter=delimiter,
        skipinitialspace=skipinitialspace,
        lineterminator=lineterminator,
        quotechar=quotechar,
        quoting=quoting,
        escapechar=escapechar,
        doublequote=doublequote
    )


@algorithm.command(cls=ViewCommand, name='update_clustering_settings')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to update.')
@click.option('--max_clusters', '-mc', type=int, required=False,
              help='Max number of possible clusters per day. [1-10]')
@click.option('--wcss_kmeans_init', '-wki',
              type=click.Choice(AVAILABLE_KMEANS_INIT), required=False,
              help='Method for clustering initialization')
@click.option('--wcss_kmeans_max_iter', '-wkmi', type=int, required=False,
              help='Maximum number of iterations of the k-means '
                   'algorithm for a single run. [1-1000]')
@click.option('--wcss_kmeans_n_init', '-wkni', type=int, required=False,
              help='Number of times the k-means algorithm is run '
                   'with different centroid seeds. [1-100]')
# todo
@click.option('--knee_interp_method', '-kim',
              type=click.Choice(AVAILABLE_KNEE_INTERP_OPTIONS),
              help='Interpolation method for fitting a spline to the input.')
@click.option('--knee_polynomial_degree', '-kpd', type=int, required=False,
              help='Controls the degree of the polynomial fit. Only for '
                   '"polynomial" interpolation method. [1-20]')
@cli_response()
def update_clustering_settings(algorithm_name, max_clusters, wcss_kmeans_init,
                               wcss_kmeans_max_iter, wcss_kmeans_n_init,
                               knee_interp_method, knee_polynomial_degree):
    """
    Updates a R8s algorithm clustering settings.
    """
    from r8scli.service.initializer import init_configuration

    optional_parameters = (max_clusters, wcss_kmeans_init,
                           wcss_kmeans_max_iter, wcss_kmeans_n_init,
                           knee_interp_method, knee_polynomial_degree)
    if not any(parameter_not_specified(param) for param
               in optional_parameters):
        response = {'message': "At least one of the optional "
                               "parameters must be specified"}
        return LocalCommandResponse(body=response)

    return init_configuration().algorithm_patch_clustering_settings(
        algorithm_name=algorithm_name,
        max_clusters=max_clusters,
        wcss_kmeans_init=wcss_kmeans_init,
        wcss_kmeans_max_iter=wcss_kmeans_max_iter,
        wcss_kmeans_n_init=wcss_kmeans_n_init,
        knee_interp_method=knee_interp_method,
        knee_polynomial_degree=knee_polynomial_degree
    )


@algorithm.command(cls=ViewCommand, name='update_recommendation_settings')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to update.')
@click.option('--record_step_minutes', '-rsm', type=int, required=False,
              help='Group metrics to specific step before processing [1-60].')
@click.option('--threshold', '-thr', multiple=True, type=int, required=False,
              help='Load thresholds used to divide clusters. '
                   'Exactly 3 values required [0-100].')
@click.option('--min_allowed_days', '-mind',
              type=int, required=False,
              help='Minimum allowed number of days data to process [1-90]')
@click.option('--max_days', '-maxd', type=int, required=False,
              help='Maximum number of days to process for a single '
                   'instance. [7-365]')
@click.option('--min_allowed_days_schedule', '-minds', type=int,
              required=False,
              help='Minimum required number of days data to allow schedule '
                   'detection. [7-60]')
@click.option('--ignore_savings', '-igs', type=bool, required=False,
              help='If True, saving calculation step will be skipped')
@click.option('--max_recommended_shapes', '-maxsh', type=int, required=False,
              help='Maximum number of shapes to recommend for single '
                   'instance. [1-10]')
@click.option('--shape_compatibility_rule', '-scr',
              type=click.Choice(AVAILABLE_SHAPE_COMPATIBILITY_RULES),
              required=False, help='Shape compatibility rule to apply for '
                                   'instances while checking their '
                                   'compatibility with current instance type')
@click.option('--shape_sorting', '-ss',
              type=click.Choice(AVAILABLE_SHAPE_SORTING),
              required=False, help='Sort recommended shapes by PRICE '
                                   '(cheaper first) or '
                                   'PERFORMANCE (most suitable first)')
@click.option('--use_past_recommendations', '-upr', type=bool, required=False,
              help='Indicates to take into account previous r8s '
                   'recommendations for that instance')
@click.option('--use_instance_tags', '-uit', type=bool, required=False,
              help='Indicates to take into account provided instance tags')
@click.option('--analysis_price', '-ap', required=False,
              type=click.Choice(AVAILABLE_ANALYSIS_PRICE),
              help='Price strategy used to calculate possible savings.')
@click.option('--ignore_action', '-ia', multiple=True, required=False,
              help='Force r8s to skip specific recommendation types')
@click.option('--target_timezone_name', '-ttz', type=str, required=False,
              help='Adjust metrics for specific timezone before processing')
@click.option('--discard_initial_zeros', '-did', type=bool, required=False,
              help='Discard metrics with zero-filled values at the '
                   'beginning of processing period.', default=True)
@click.option('--forbid_change_series', '-fcs', type=bool, required=False,
              help='Forbids to recommend shapes from different series')
@click.option('--forbid_change_family', '-fcf', type=bool, required=False,
              help='Forbids to recommend shapes from different family')
@cli_response()
def update_recommendation_settings(algorithm_name, record_step_minutes,
                                   threshold,
                                   min_allowed_days, max_days,
                                   min_allowed_days_schedule, ignore_savings,
                                   max_recommended_shapes,
                                   shape_compatibility_rule,
                                   shape_sorting, use_past_recommendations,
                                   use_instance_tags, analysis_price,
                                   ignore_action,
                                   target_timezone_name,discard_initial_zeros,
                                   forbid_change_series, forbid_change_family):
    """
    Updates a R8s algorithm recommendation settings.
    """
    from r8scli.service.initializer import init_configuration

    thresholds = cast_to_list(threshold)
    if thresholds and not len(thresholds) == 3:
        response = {'message': "Exactly 3 threshold values required"}
        return LocalCommandResponse(body=response)
    ignore_actions = cast_to_list(ignore_action)
    optional_parameters = (record_step_minutes, thresholds,
                           min_allowed_days, max_days,
                           min_allowed_days_schedule, ignore_savings,
                           max_recommended_shapes, shape_compatibility_rule,
                           shape_sorting, use_past_recommendations,
                           use_instance_tags, analysis_price, ignore_actions,
                           target_timezone_name, discard_initial_zeros,
                           forbid_change_series, forbid_change_family)
    if not any(parameter_not_specified(param) for param
               in optional_parameters):
        response = {'message': "At least one of the optional "
                               "parameters must be specified"}
        return LocalCommandResponse(body=response)

    return init_configuration().algorithm_patch_recommendation_settings(
        algorithm_name=algorithm_name,
        record_step_minutes=record_step_minutes,
        thresholds=thresholds,
        min_allowed_days=min_allowed_days,
        max_days=max_days,
        min_allowed_days_schedule=min_allowed_days_schedule,
        ignore_savings=ignore_savings,
        max_recommended_shapes=max_recommended_shapes,
        shape_compatibility_rule=shape_compatibility_rule,
        shape_sorting=shape_sorting,
        use_past_recommendations=use_past_recommendations,
        use_instance_tags=use_instance_tags,
        analysis_price=analysis_price,
        ignore_actions=ignore_actions,
        target_timezone_name=target_timezone_name,
        discard_initial_zeros=discard_initial_zeros,
        forbid_change_series=forbid_change_series,
        forbid_change_family=forbid_change_family
    )


@algorithm.command(cls=ViewCommand, name='delete')
@click.option('--algorithm_name', '-name', type=str, required=True,
              help='Algorithm name to delete.')
@cli_response()
def delete(algorithm_name=None):
    """
    Deletes a R8s algorithm.
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().algorithm_delete(
        algorithm_name=algorithm_name)
