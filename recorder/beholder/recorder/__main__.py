import logging

import click # type: ignore
from click_loglevel import LogLevel  # type: ignore

from .controller import Controller
from .utils import _log, setup_logging

@click.command()
@click.argument("config_path", type=click.Path(exists=True))
@click.argument("credentials_path", type=click.Path(exists=True))
@click.option("-l", "--log-level", default=logging.INFO, type=LogLevel())
@click.option('--verbose/--silent', default=True, type=bool)
@click.option('--log_backup', default=0, type=int)
def main(config_path, credentials_path, log_level, verbose, log_backup):
    log_rotator = setup_logging(log_level, "logs/log", log_backup)
    _log().info("config_path: %s", config_path)
    controller = Controller(config_path, credentials_path, verbose=verbose)
    log_rotator.callback = controller.upload_logs
    controller.run()


if __name__ == "__main__":
    main()
