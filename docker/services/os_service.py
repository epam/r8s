import json
import os
import pathlib
import shutil
from glob import glob

from commons.constants import JOB_STEP_VALIDATE_METRICS, CSV_EXTENSION
from commons.exception import ExecutorException
from commons.log_helper import get_logger
from models.algorithm import Algorithm

_LOG = get_logger('r8s-os-service')


class OSService:
    def __init__(self):
        self.r8s_workdir = str(pathlib.Path(__file__).parent.parent.absolute())

    def create_work_dirs(self, job_id):
        _LOG.debug(f'Creating job directory')
        work_dir = self.create_workdir(job_id=job_id)

        _LOG.debug(f'Creating metrics directory')
        metrics_dir = self.create_job_dir(work_dir=work_dir,
                                          dir_name='metrics')
        _LOG.debug(f'Creating reports directory')
        reports_dir = self.create_job_dir(work_dir=work_dir,
                                          dir_name='reports')

        _LOG.debug(f'Job dir: \'{work_dir}\', metrics dir: \'{metrics_dir}\', '
                   f'reports dir: \'{reports_dir}\'')
        return work_dir, metrics_dir, reports_dir

    def create_workdir(self, job_id):
        temp_dir = os.path.join(self.r8s_workdir, job_id)
        os.chdir(str(pathlib.Path(temp_dir).parent))
        pathlib.Path(temp_dir).mkdir(exist_ok=True)
        return temp_dir

    @staticmethod
    def create_job_dir(work_dir, dir_name):
        temp_dir = os.path.join(work_dir, dir_name)
        os.chdir(str(pathlib.Path(temp_dir).parent))
        pathlib.Path(temp_dir).mkdir(exist_ok=True)
        return temp_dir

    @staticmethod
    def clean_workdir(work_dir):
        shutil.rmtree(work_dir)
        _LOG.debug(f'Workdir for {work_dir} successfully cleaned')

    @staticmethod
    def write_file(content, file_path):
        if isinstance(content, dict):
            content = json.dumps(content)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path

    @staticmethod
    def extract_metric_files(algorithm: Algorithm, metrics_folder_path):
        if not algorithm.required_data_attributes:
            _LOG.debug(f'No required data attributes specified for algorithm '
                       f'\'{algorithm.name}\'.')
            return
        metric_files = [y for x in os.walk(metrics_folder_path)
                        for y in glob(os.path.join(x[0], '*.csv'))]
        return metric_files

    @staticmethod
    def path_to_instance_id(file_path):
        file_name = file_path.split(os.sep)
        if len(file_name) < 1:
            _LOG.warning(f'Invalid file path provided: \'{file_path}\'')
            return
        file_name = file_name[-1]
        if not file_name.endswith(CSV_EXTENSION):
            _LOG.warning(f'Not a metric file: \'{file_path}\'')
            return
        instance_id = file_name.replace(CSV_EXTENSION, '')
        return instance_id

    @staticmethod
    def path_to_cloud(file_path):
        return file_path.split(os.sep)[-5]

    @staticmethod
    def path_to_tenant(file_path):
        return file_path.split(os.sep)[-4]

    def group_by_tenant(self, file_paths: list):
        tenant_metrics_map = {}
        for file_path in file_paths:
            tenant = self.path_to_tenant(file_path=file_path)
            tenant_metrics_map[tenant] = file_path
        return tenant_metrics_map
