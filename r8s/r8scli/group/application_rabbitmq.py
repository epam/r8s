import click

from r8scli.group import cli_response, ViewCommand


@click.group(name='rabbitmq')
def rabbitmq():
    """Manages RIGHTSIZER_RABBITMQ Application Entity"""


@rabbitmq.command(cls=ViewCommand, name='describe')
@click.option('--application_id', '-aid', type=str, required=False,
              help='Id of the application to describe')
@cli_response()
def describe(application_id=None):
    """
    Describes a RIGHTSIZER_RABBITMQ Application
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_rabbitmq_get(
        application_id=application_id,
    )


@rabbitmq.command(cls=ViewCommand, name='add')
@click.option('--customer_id', '-cid', type=str, required=True,
              help='Maestro Customer name')
@click.option('--description', '-d', type=str, required=True,
              help='Application description')
@click.option('--connection_url', '-url', type=str, required=True,
              help='RabbitMQ AMQP connection URL (e.g. amqp://user:pass@host/)')
@click.option('--request_queue', '-req', type=str, required=True,
              help='RabbitMQ request queue name')
@click.option('--response_queue', '-res', type=str, required=True,
              help='RabbitMQ response queue name')
@click.option('--sdk_access_key', '-sak', type=str, required=True,
              help='SDK access key')
@click.option('--sdk_secret_key', '-ssk', type=str,
              required=True, hide_input=True, prompt=True,
              help='SDK secret key. If not provided, will be prompted securely')
@click.option('--maestro_user', '-mu', type=str, required=True,
              help='Maestro user')
@click.option('--rabbit_exchange', '-re', type=str, required=False,
              help='RabbitMQ exchange name')
@cli_response()
def add(customer_id, description, connection_url, request_queue,
        response_queue, sdk_access_key, sdk_secret_key,
        maestro_user, rabbit_exchange):
    """
    Creates a RIGHTSIZER_RABBITMQ Application
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_rabbitmq_post(
        customer=customer_id,
        description=description,
        connection_url=connection_url,
        request_queue=request_queue,
        response_queue=response_queue,
        sdk_access_key=sdk_access_key,
        sdk_secret_key=sdk_secret_key,
        maestro_user=maestro_user,
        rabbit_exchange=rabbit_exchange,
    )


@rabbitmq.command(cls=ViewCommand, name='delete')
@click.option('--application_id', '-aid', type=str, required=True,
              help='Id of the application to delete')
@click.option('--force', '-f', is_flag=True,
              help='Completely delete Application from db')
@cli_response()
def delete(application_id, force):
    """
    Deletes a RIGHTSIZER_RABBITMQ Application
    """
    from r8scli.service.initializer import init_configuration
    return init_configuration().application_rabbitmq_delete(
        application_id=application_id,
        force=force,
    )


rabbitmq.add_command(describe)
rabbitmq.add_command(add)
rabbitmq.add_command(delete)
