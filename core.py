import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from multiprocessing import Process

from . import git

__all__ = ['FlaskAppConfig']

logger = logging.getLogger('waitress')
logger.setLevel(logging.DEBUG)

REPO_URL_PATTERN = re.compile(r'https:\/\/github\.com\/[a-zA-Z0-9\-]+\/[a-zA-Z0-9\-_]+\.git')


@dataclass
class FlaskAppConfig:
    directory: str  # directory to clone
    repo: str  # github repository URL
    app_file: str = 'app.py'  # path to the app file in repository
    app_name: str = 'app'  # app variable name
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    def __post_init__(self):
        # validate
        if not REPO_URL_PATTERN.fullmatch(self.repo):
            raise ValueError(
                f'Invalid URL: "{self.repo}". '
                'Must match format: https://github.com/user/repo'
            )

    @property
    def path(self) -> str:
        return os.path.join(self.directory, self.app_file)


class AppManager:
    """
    Manages Flask app and git
    """
    def __init__(self, config: FlaskAppConfig):
        self.config = config
        if not os.path.exists(config.directory):
            self.clone()
        else:
            self.pull()

    def clone(self) -> None:
        git.clone(self.config.repo, self.config.directory)

    def pull(self) -> None:
        git.pull(self.config.directory)

    def apply_module_path(self):
        abs_path = os.path.abspath(self.config.path)
        dir_name = os.path.dirname(abs_path)
        if dir_name not in sys.path:
            sys.path.insert(0, dir_name)

    def import_app(self):
        self.apply_module_path()
        spec = importlib.util.spec_from_file_location('app', self.config.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, self.config.app_name)

    # def run_with_flask(self):
    #     app = self.import_app()
    #     app.run(*self.config.args, **self.config.kwargs)

    def run_with_waitress(self):
        os.chdir(self.config.directory)
        from waitress import serve
        app = self.import_app()
        serve(app, *self.config.args, **self.config.kwargs)


@dataclass
class AppProcess:
    """
    Manages single process.
    """
    app: AppManager
    process: Process | None = None

    def start_process(self) -> None:
        process = Process(target=self.app.run_with_waitress)
        process.start()
        self.process = process

    def kill_process(self) -> None:
        if not self.process:
            return
        self.process.kill()
        self.process = None

    def update(self) -> None:
        self.kill_process()
        self.app.pull()
        self.start_process()


class ProcessManager:
    """
    A class to contain multiple processes.
    """
    def __init__(self, configs: list[FlaskAppConfig]):
        self.app_processes: dict[str, AppProcess] = {}
        self.initialize_all_processes(configs)

    def initialize_all_processes(self, configs: list[FlaskAppConfig]):
        for config in configs:
            self.app_processes[config.repo] = AppProcess(
                AppManager(config)
            )

    def start_all_processes(self) -> None:
        for state in self.app_processes.values():
            state.start_process()
