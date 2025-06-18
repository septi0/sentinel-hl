import os
import logging
import signal
import yaml
import datetime
import asyncio
from logging.handlers import TimedRotatingFileHandler
from sentinel_hl.exceptions import SentinelHlRuntimeError, ExitSignal, SIGHUPSignal
from sentinel_hl.libraries.datastore import Datastore
from sentinel_hl.libraries.cmd_exec import CmdExec, CmdExecProcessError
from sentinel_hl.models.sentinel_nl import SentinelHlModel
from sentinel_hl.services.wol import WolService
from sentinel_hl.services.host import HostService
from sentinel_hl.services.ups import UpsService

__all__ = ['SentinelHlManager']

class SentinelHlManager:
    def __init__(self, *, log_file: str = '', log_level: str = '', config_file: str = '') -> None:
        self._log_file: str = log_file
        self._log_level: str = log_level
        self._config_file: str = config_file
        
        self._logger: logging.Logger = self._logger_factory(self._log_file, self._log_level)
        self._pid_filepath: str = self._get_pid_filepath()
        
        self._init()

    def run_once(self) -> None:
        self._run_main(self._do_run_once)
    
    def run_forever(self) -> None:
        self._run_main(self._do_run_forever)
    
    def clear_cache(self) -> None:
        self._hosts_datastore.clear()
        self._ups_datastore.clear()
        
        self._logger.info("All caches cleared")
        
        self._run_main(self._send_reload_signal)
        
    def reload(self) -> None:
        self._logger.info("Reloading the running service")

        self._run_main(self._send_reload_signal)
        
    def _init(self) -> None:
        self._config: SentinelHlModel = SentinelHlModel(**self._load_config(file=self._config_file))
        self._hosts_datastore: Datastore = Datastore(self._get_datastore_filepath('hosts'))
        self._ups_datastore: Datastore = Datastore(self._get_datastore_filepath('ups'))
        self._hosts: list[HostService] = self._hosts_factory()
        self._ups_units: list[UpsService] = self._ups_units_factory()

    def _load_config(self, *, file: str = '') -> dict:
        config_files = [
            '/etc/sentinel-hl/config.yml',
            '/etc/opt/sentinel-hl/config.yml',
            os.path.expanduser('~/.config/sentinel-hl/config.yml'),
        ]
        
        if file:
            config_files = [file]
            
        file_to_load = None
        
        for config_file in config_files:
            if os.path.isfile(config_file):
                file_to_load = config_file
                break
       
        if not file_to_load:
            raise SentinelHlRuntimeError("No config file found")
        
        with open(file_to_load, 'r') as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise SentinelHlRuntimeError(f"Failed to parse config file: {e}")
            
        return config
        
    def _get_pid_filepath(self) -> str:
        if os.getuid() == 0:
            return '/var/run/sentinel-hl.pid'
        else:
            return os.path.expanduser('~/.sentinel-hl.pid')

    def _get_datastore_filepath(self, name: str) -> str:
        if os.getuid() == 0:
            filepath = f'/var/opt/sentinel-hl/{name}.db'
        else:
            filepath = os.path.expanduser(f'~/.sentinel-hl/{name}.db')

        directory = os.path.dirname(filepath)
        
        if not os.path.exists(directory):
            os.makedirs(directory)
            
        return filepath
    
    def _logger_factory(self, log_file: str, log_level: str) -> logging.Logger:
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        if not log_level in levels:
            log_level = "INFO"

        logger = logging.getLogger()
        logger.setLevel(levels[log_level])

        if log_file:
            directory = os.path.dirname(log_file)
            
            if not os.path.exists(directory):
                os.makedirs(directory)
            
            handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=4)
        else:
            handler = logging.StreamHandler()

        handler.setLevel(levels[log_level])
        handler.setFormatter(logging.Formatter(format))

        logger.addHandler(handler)

        return logger

    def _wol_factory(self) -> WolService:
        wol_logger = self._logger.getChild('wol')
        
        return WolService(self._config.wol, logger=wol_logger)
    
    def _hosts_factory(self) -> list[HostService]:
        hosts_logger = self._logger.getChild('host')
        wol = self._wol_factory()

        instances = []
        
        for host in self._config.hosts:
            instances.append(HostService(host, self._config.hosts_policy, datastore=self._hosts_datastore, wol=wol, logger=hosts_logger))

        return instances
    
    def _ups_units_factory(self) -> list[UpsService]:
        ups_logger = self._logger.getChild('ups')
        
        instances = []
        
        for ups in self._config.ups:
            ups_hosts = [host for host in self._hosts if host.name in ups.hosts]
            
            if not ups_hosts:
                self._logger.warning(f'UPS "{ups.name}" has no hosts configured. Skipping')
                continue
            
            instances.append(UpsService(ups, ups_hosts, self._config.ups_units_policy, datastore=self._ups_datastore, logger=ups_logger))
            
        return instances
    
    def _exit_signal_handler(self) -> None:
        raise ExitSignal
    
    def _sighup_signal_handler(self) -> None:
        raise SIGHUPSignal
    
    def _run_main(self, main_task, *args, **kwargs) -> None:
        run = True
        
        while run:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.add_signal_handler(signal.SIGTERM, self._exit_signal_handler)
            loop.add_signal_handler(signal.SIGINT, self._exit_signal_handler)
            loop.add_signal_handler(signal.SIGQUIT, self._exit_signal_handler)
            
            # on signal SIGHUP, reinitialize all data
            loop.add_signal_handler(signal.SIGHUP, self._sighup_signal_handler)

            try:
                loop.run_until_complete(main_task(*args, **kwargs))
                run = False
            except (SIGHUPSignal) as e:
                self._logger.info("Received SIGHUP signal")
                # reinitialize all data
                self._init()
            except (ExitSignal) as e:
                self._logger.info("Received termination signal")
                run = False
            except (Exception) as e:
                self._logger.exception(e)
                run = False
            finally:
                loop.run_until_complete(self._disconnect_ups_units())
                        
                try:
                    if os.path.isfile(self._pid_filepath):
                        os.remove(self._pid_filepath)
                    
                    self._cancel_tasks(loop)
                    loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()

    def _cancel_tasks(self, loop: asyncio.AbstractEventLoop) -> None:
        tasks = asyncio.all_tasks(loop=loop)

        if not tasks:
            return

        for task in tasks:
            task.cancel()

        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

        for task in tasks:
            if task.cancelled():
                continue

            if task.exception() is not None:
                loop.call_exception_handler({
                    'message': 'Unhandled exception during task cancellation',
                    'exception': task.exception(),
                    'task': task,
                })
                
    async def _do_run_once(self) -> None:
        self._logger.info("Running discovery and checks")
        
        await self._discover_hosts()
        await self._poll_ups_units()
        await self._check_hosts(run_discovery = False)
        
        return

    async def _do_run_forever(self) -> None:
        # run as service
        pid = str(os.getpid())

        if os.path.isfile(self._pid_filepath):
            self._logger.error("Service is already running")
            return

        with open(self._pid_filepath, 'w') as f:
            f.write(pid)

        self._logger.info(f'Starting service with pid {pid}')
        
        tasks = []
        
        self._logger.info("Running initial discovery and checks")
        
        await self._discover_hosts()
        await self._poll_ups_units()
        await self._check_hosts(run_discovery = False)
        
        self._logger.info("Starting periodic tasks")
        tasks.append(asyncio.create_task(self._poll_ups_units_task()))
        tasks.append(asyncio.create_task(self._check_hosts_task()))

        await asyncio.gather(*tasks, return_exceptions=True)
        
        for task in tasks:
            if task.cancelled():
                continue

            if task.exception() is not None:
                self._logger.error(f'Task failed with exception: {task.exception()}')

    async def _poll_ups_units_task(self) -> None:
        run_time = datetime.datetime.now().replace(microsecond=0)
        
        if not self._ups_units:
            self._logger.info("No UPS units configured. Skipping UPS polling task")
            return

        while True:
            # calculate the next scheduled run_time
            run_time += datetime.timedelta(seconds=self._config.ups_poll_interval)
            
            # calculate the time left until the next run_time
            time_left = (run_time - datetime.datetime.now()).total_seconds()

            if time_left > 0:
                self._logger.debug(f'UPS polling in {time_left} s')
                await asyncio.sleep(time_left)
            else:
                self._logger.debug('Running UPS polling now')
                run_time = datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(seconds=self._config.ups_poll_interval)
                
            await self._poll_ups_units()
            
    async def _check_hosts_task(self) -> None:
        run_time = datetime.datetime.now().replace(microsecond=0)

        while True:
            # calculate the next scheduled run_time
            run_time += datetime.timedelta(seconds=self._config.hosts_check_interval)

            # calculate the time left until the next run_time
            time_left = (run_time - datetime.datetime.now()).total_seconds()

            if time_left > 0:
                self._logger.debug(f'Hosts check run in {time_left} s')
                await asyncio.sleep(time_left)
            else:
                self._logger.debug('Running hosts check now')
                run_time = datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(seconds=self._config.hosts_check_interval)
                
            await self._check_hosts()
            
    async def _discover_hosts(self) -> None:
        for host in self._hosts:
            try:
                await host.discover()
            except Exception as e:
                self._logger.exception(e)
                
    async def _poll_ups_units(self) -> None:
        for ups in self._ups_units:
            try:
                await ups.poll()
            except Exception as e:
                self._logger.exception(e)

    async def _check_hosts(self, run_discovery: bool = True) -> None:
        for host in self._hosts:
            try:
                if run_discovery:
                    await host.discover()
                    
                await host.check()
            except Exception as e:
                self._logger.exception(e)
    
    async def _disconnect_ups_units(self) -> None:
        for ups in self._ups_units:
            try:
                await ups.disconnect()
            except Exception as e:
                self._logger.exception(e)
                
    async def _send_reload_signal(self) -> None:
        if not os.path.isfile(self._pid_filepath):
            return
        
        with open(self._pid_filepath, 'r') as f:
            pid = f.read().strip()
            
        if not pid.isdigit():
            self._logger.error(f'Invalid PID in {self._pid_filepath}: {pid}')
            return
            
        try:
            await CmdExec.exec(['kill', '-HUP', pid])
            self._logger.info(f'Sent reload signal to process {pid}')
        except CmdExecProcessError as e:
            self._logger.error(f'Failed to send reload signal to process {pid}: {e}')