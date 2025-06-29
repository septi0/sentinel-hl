import os
import sys
import logging
import signal
import yaml
import datetime
import asyncio
from logging.handlers import TimedRotatingFileHandler
from sentinel_hl.exceptions import SentinelHlRuntimeError, ExitSignal, SIGHUPSignal
from sentinel_hl.utils.logging import NoExceptionFormatter
from sentinel_hl.libraries.cleanup_queue import CleanupQueue
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

    def run_once(self) -> None:
        self._run_main(self._do_run_once)
    
    def run_forever(self) -> None:
        self._run_main(self._do_run_forever)
    
    def clear_cache(self) -> None:
        self._run_main(self._do_clear_cache)
        
    def reload(self) -> None:
        self._run_main(self._do_reload)
        
    def ack_host(self, name: str, clear: bool = False) -> None:
        self._run_main(self._do_ack_host, name, clear=clear)

    def _init(self) -> None:
        self._config: SentinelHlModel = SentinelHlModel(**self._load_config(file=self._config_file))
        self._cleanup: CleanupQueue = CleanupQueue()
        self._hosts_datastore: Datastore = Datastore(self._get_datastore_filepath('hosts'))
        self._ups_datastore: Datastore = Datastore(self._get_datastore_filepath('ups'))
        self._hosts: list[HostService] = self._hosts_factory()
        self._ups_units: list[UpsService] = self._ups_units_factory()

    def _load_config(self, *, file: str = '') -> dict:
        config_files = [
            '/config/config.yml',
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
    
    def _is_venv(self) -> bool:
        return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)
        
    def _get_pid_filepath(self) -> str:
        if os.getuid() == 0:
            return '/var/run/sentinel-hl.pid'
        else:
            return os.path.expanduser('~/.sentinel-hl.pid')

    def _get_datastore_filepath(self, name: str) -> str:
        if self._is_venv():
            filepath = os.path.join(sys.prefix, 'var', f'{name}.db')
        elif os.getuid() == 0:
            filepath = f'/var/lib/sentinel-hl/{name}.db'
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
        
        if log_level == "DEBUG":
            handler.setFormatter(logging.Formatter(format))
        else:
            handler.setFormatter(NoExceptionFormatter(format))

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
            self._init()
            
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
            except (ExitSignal) as e:
                self._logger.info("Received termination signal")
                run = False
            except (Exception) as e:
                self._logger.exception(e)
                run = False
            finally:
                if self._cleanup.has_jobs:
                    try:
                        self._logger.info("Running cleanup jobs")
                        loop.run_until_complete(self._cleanup.consume_all())
                    except Exception as e:
                        self._logger.exception(f"Error during cleanup: {e}")
                        
                try:
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
        self._logger.info("Sentinel-Hl started")
        
        await self._discover_hosts()
        await self._poll_ups_units()
        await self._check_hosts(run_discovery = False)
        await self._disconnect_ups_units()
        
        return

    async def _do_run_forever(self) -> None:
        # run as service
        pid = str(os.getpid())
        pid_filepath: str = self._get_pid_filepath()

        if os.path.isfile(pid_filepath):
            self._logger.error("Service is already running")
            return

        with open(pid_filepath, 'w') as f:
            f.write(pid)
        
        # register shutdown task that will remove the pid file
        self._cleanup.push('remove_service_pid', os.remove, pid_filepath)

        self._logger.info(f'Sentinel-Hl daemon started with pid {pid}')
        
        tasks = []
        
        await self._discover_hosts()
        await self._poll_ups_units()
        await self._check_hosts(run_discovery = False)
        
        self._cleanup.push('disconnect_ups_units', self._disconnect_ups_units)
        
        self._logger.info("Polling for new events...")
        
        tasks.append(asyncio.create_task(self._poll_ups_units_task()))
        tasks.append(asyncio.create_task(self._check_hosts_task()))

        await asyncio.gather(*tasks, return_exceptions=True)
        
        for task in tasks:
            if task.cancelled():
                continue

            if task.exception() is not None:
                self._logger.exception(f'Task failed with exception: {task.exception()}')

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
                self._logger.debug(f'Sleeping for {time_left}s until next UPS poll')
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
                self._logger.debug(f'Sleeping for {time_left}s until next hosts check')
                await asyncio.sleep(time_left)
            else:
                self._logger.debug('Running hosts check now')
                run_time = datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(seconds=self._config.hosts_check_interval)
                
            await self._check_hosts()
            
    async def _discover_hosts(self) -> None:
        self._logger.info("Running initial hosts discovery...")
        
        for host in self._hosts:
            try:
                await host.discover()
                self._logger.info(f'Host "{host.name}" ip: {host.ip}, MAC: {host.mac}')
                
                if host.acknowledged:
                    self._logger.warning(f'Host "{host.name}" is acknowledged as down. Won\'t check its status')
            except Exception as e:
                self._logger.warning(f'Discovery failed for host "{host.name}": {e}')
                
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
            if not ups.connected:
                continue
                
            try:
                await ups.disconnect()
            except Exception as e:
                self._logger.exception(e)
                
    async def _do_clear_cache(self) -> None:
        self._hosts_datastore.clear()
        self._ups_datastore.clear()
        
        self._logger.info("All caches cleared")
        
        await self._send_reload_signal()
        
    async def _do_reload(self) -> None:
        self._logger.info("Reloading the running service")

        await self._send_reload_signal()
        
    async def _do_ack_host(self, name: str, clear: bool = False) -> None:
        if not name:
            self._logger.error("No host specified to acknowledge")
            return
        
        for host in self._hosts:
            if host.name == name:
                try:
                    if clear:
                        host.clear_ack()
                        self._logger.info(f'Host "{host}" acknowledgment cleared')
                    else:
                        host.ack()
                        self._logger.info(f'Host "{host}" acknowledged down')
                except Exception as e:
                    self._logger.error(f'Failed to acknowledge host "{host}": {e}')
                    
                await self._send_reload_signal()
                    
                return
        
        self._logger.error(f'Host "{host}" not found in configuration')

    async def _send_reload_signal(self) -> None:
        pid_filepath: str = self._get_pid_filepath()

        if not os.path.isfile(pid_filepath):
            return

        with open(pid_filepath, 'r') as f:
            pid = f.read().strip()
            
        if not pid.isdigit():
            self._logger.error(f'Invalid PID in {pid_filepath}: {pid}')
            return
            
        try:
            await CmdExec.exec(['kill', '-HUP', pid])
            self._logger.info(f'Sent reload signal to process {pid}')
        except CmdExecProcessError as e:
            self._logger.error(f'Failed to send reload signal to process {pid}: {e}')