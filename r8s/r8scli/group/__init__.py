import json
import os
from functools import wraps
from pathlib import Path

import click
from prettytable import PrettyTable

from r8scli.service.exception import HTTP_CODE_EXCEPTION_MAPPING, \
    R8sInternalException
from r8scli.service.logger import get_logger, get_user_logger, FILE_NAME

POSITIVE_ANSWERS = ['y', 'yes']
CONFIRMATION_MESSAGE = 'The command`s response is pretty huge and the ' \
                       'result table structure can be broken.\nDo you want ' \
                       'to show the response in the JSON format? [y/n]: '

MAX_COLUMNS_WIDTH = 30
CLI_VIEW = 'cli'
JSON_VIEW = 'json'
TABLE_VIEW = 'table'
ERROR_STATUS = 'FAILED'
API_MODE_KEY = 'api_mode'
CLOUD_ADMIN_CODE = 'Code'
MODULAR_ADMIN = 'modules'
SUCCESS_STATUS = 'SUCCESS'
TABLE_TITLE = 'table_title'
R8S_ITEMS = 'items'
R8S_STATUS = 'Status'
R8S_MESSAGE = 'Message'
R8S_WARNINGS = 'Warnings'
R8S_RESPONSE = 'Response'
R8S_MESSAGE_LOW = 'message'
R8S_ERROR_TYPE = 'ErrorType'
R8S_WARNINGS_LOW = 'warnings'
R8S_TABLE_TITLE = 'table_title'

SYSTEM_LOG = get_logger('R*S.r8s_group')
USER_LOG = get_user_logger('user')

HTTP_GET = 'get'
HTTP_POST = 'post'
HTTP_DELETE = 'delete'
HTTP_PATCH = 'patch'


class ViewCommand(click.core.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(
            len(self.params),
            click.core.Option(
                ('--json',), is_flag=True,
                help='Use this parameter to show command`s response in a '
                     'JSON view.'))
        self.params.insert(
            len(self.params),
            click.core.Option(
                ('--table',), is_flag=True,
                help='Use this parameter to show command`s response in a '
                     'Table view.'))

    def main(self, *args, **kwargs):
        try:
            return super().main(*args, **kwargs)
        except Exception as e:
            raise R8sInternalException(str(e))


def cli_response(id_attribute=None, secured_params=None, reversed=False):
    def internal(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            modular_mode = False
            if Path(__file__).parents[3].name == 'modules':
                modular_mode = True

            view_format = CLI_VIEW
            table_format = kwargs.pop(TABLE_VIEW, False)
            json_format = kwargs.pop(JSON_VIEW, False)
            response = func(*args, **kwargs)

            if modular_mode or json_format:
                view_format = JSON_VIEW
            elif table_format:
                view_format = TABLE_VIEW
            pretty_response = ResponseFormatter(function_result=response,
                                                view_format=view_format). \
                prettify_response(reversed=reversed)
            if modular_mode:
                return pretty_response
            else:
                click.echo(pretty_response)

        return wrapper

    return internal


class ResponseFormatter:
    def __init__(self, function_result, view_format):
        self.view_format = view_format
        self.function_result = function_result
        self.format_to_process_method = {
            CLI_VIEW: self.process_cli_view,
            JSON_VIEW: self.process_json_view,
            TABLE_VIEW: self.process_table_view
        }

    @staticmethod
    def _prettify_warnings(warnings: list):
        return f'{os.linesep}WARNINGS:{os.linesep}' + \
               f'{os.linesep}'.join([str(i + 1) + '. ' + warnings[i]
                                     for i in range(len(warnings))])

    @staticmethod
    def is_response_success(response_meta):
        if response_meta.status_code == 200 or \
                response_meta.status_code in HTTP_CODE_EXCEPTION_MAPPING:
            return True
        return False

    @staticmethod
    def unpack_success_result_values(response_meta):
        success_code = response_meta.status_code
        response_body = json.loads(response_meta.text)
        message = response_body.get(R8S_MESSAGE_LOW) or \
                  response_body.get(R8S_MESSAGE)
        items = response_body.get(R8S_ITEMS)
        warnings = response_body.get(R8S_WARNINGS_LOW)
        return success_code, warnings, message, items

    @staticmethod
    def unpack_error_result_values(response_meta):
        error_code = response_meta.status_code
        response_body = json.loads(response_meta.text)
        error_message = response_body.get(R8S_MESSAGE_LOW)
        error_type = HTTP_CODE_EXCEPTION_MAPPING[error_code].__name__
        return error_type, error_code, error_message

    def process_cli_view(self, status, response_meta, reversed=False):
        if status == ERROR_STATUS:
            error_type, error_code, message = self.unpack_error_result_values(
                response_meta=response_meta)
            return f'Error:{os.linesep}{message}' \
                   f'{os.linesep}See detailed info and traceback in ' \
                   f'{os.path.join(FILE_NAME)}'
        elif status == SUCCESS_STATUS:
            success_code, warnings, message, items = \
                self.unpack_success_result_values(response_meta=response_meta)
            if items:
                return self.process_table_view(status=status,
                                               response_meta=response_meta,
                                               reversed=reversed)
            result_message = f'Response:{os.linesep}{message}'
            if warnings:
                result_message += self._prettify_warnings(warnings)
            return result_message

    def process_json_view(self, status, response_meta, reversed=False):
        if status == ERROR_STATUS:
            error_type, error_code, message = self.unpack_error_result_values(
                response_meta=response_meta)
            return json.dumps({
                R8S_STATUS: status,
                CLOUD_ADMIN_CODE: error_code,
                R8S_ERROR_TYPE: error_type,
                R8S_MESSAGE: message
            }, indent=4)
        elif status == SUCCESS_STATUS:
            success_code, warnings, message, items = \
                self.unpack_success_result_values(response_meta=response_meta)
            if items:
                if reversed:
                    items = items[::-1]
                return json.dumps({
                    R8S_STATUS: status,
                    CLOUD_ADMIN_CODE: success_code,
                    R8S_TABLE_TITLE: 'RESPONSE',
                    R8S_ITEMS: items,
                    R8S_WARNINGS: warnings
                }, indent=4)
            return json.dumps({
                R8S_STATUS: status,
                CLOUD_ADMIN_CODE: success_code,
                R8S_MESSAGE: message,
                R8S_WARNINGS: warnings
            }, indent=4)

    def process_table_view(self, status, response_meta, reversed=False):
        response = PrettyTable()
        if status == ERROR_STATUS:
            response.field_names = [R8S_STATUS,
                                    CLOUD_ADMIN_CODE,
                                    R8S_MESSAGE]
            response._max_width = {R8S_STATUS: 10,
                                   CLOUD_ADMIN_CODE: 5,
                                   R8S_MESSAGE: 70}
            error_type, error_code, message = self.unpack_error_result_values(
                response_meta=response_meta)
            response.add_row([status, error_code, message])
            response = response.__str__()
            return response
        elif status == SUCCESS_STATUS:
            success_code, warnings, message, items = \
                self.unpack_success_result_values(
                    response_meta=response_meta)

            if message:
                response.field_names = [R8S_STATUS,
                                        CLOUD_ADMIN_CODE,
                                        R8S_RESPONSE]
                response._max_width = {R8S_STATUS: 10,
                                       CLOUD_ADMIN_CODE: 5,
                                       R8S_RESPONSE: 70}
                response.add_row([status, success_code, message])
            elif items:
                all_values = {}
                uniq_table_headers = []
                width_table_columns = {}
                if reversed:
                    items = items[::-1]
                for each_item in items:
                    if not isinstance(each_item, dict):
                        each_item = {'Result': each_item}
                    for table_key, table_value in each_item.items():
                        if all_values.get(table_key):
                            all_values[table_key].append(table_value)
                        else:
                            all_values[table_key] = [table_value]
                        uniq_table_headers.extend(
                            [table_key for table_key in
                             each_item.keys()
                             if table_key not in uniq_table_headers])
                        if not width_table_columns.get(table_key) \
                                or width_table_columns.get(table_key) \
                                < len(str(table_value)):
                            width_table_columns[table_key] \
                                = len(str(table_value))
                import itertools
                response.field_names = uniq_table_headers
                response._max_width = {each: MAX_COLUMNS_WIDTH for each in
                                       uniq_table_headers}
                try:
                    if MAX_COLUMNS_WIDTH * len(uniq_table_headers) > \
                            os.get_terminal_size().columns and \
                            input(CONFIRMATION_MESSAGE).lower().strip() \
                            in POSITIVE_ANSWERS:
                        return self.process_json_view(
                            status, response_meta, reversed)
                except Exception:
                    pass
                last_string_index = 0
                # Fills with an empty content absent items attributes to
                # align the table
                table_rows = itertools.zip_longest(
                    *[j for i, j in all_values.items()], fillvalue='')
                for lst in table_rows:
                    response.add_row(lst)
                    row_separator = ['-' * min(
                        max(width_table_columns[uniq_table_headers[i]],
                            len(str(uniq_table_headers[i]))),
                        30) for i in range(len(uniq_table_headers))]
                    response.add_row(row_separator)
                    last_string_index += 2
                response.del_row(last_string_index - 1)

            response = str(response)
            if warnings:
                response += self._prettify_warnings(warnings)

        return response

    def prettify_response(self, reversed=None):
        status = SUCCESS_STATUS if self.is_response_success(
            response_meta=self.function_result) else ERROR_STATUS
        view_processor = self.format_to_process_method[self.view_format]
        prettified_response = view_processor(
            status=status,
            response_meta=self.function_result,
            reversed=reversed)
        return prettified_response



def cast_to_list(input):
    if type(input) == tuple:
        list_item = list(input)
    elif type(input) == str:
        list_item = [input]
    else:
        list_item = input
    return list_item