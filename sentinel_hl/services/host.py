import logging
import asyncio
import socket
import re
from sentinel_hl.libraries.datastore import Datastore
from sentinel_hl.libraries.host_discovery import HostDiscovery
from sentinel_hl.libraries.cmd_exec import CmdExec, CmdExecHost, CmdExecProcessError
from sentinel_hl.models.host import HostModel
from sentinel_hl.models.hosts_policy import HostsPolicyModel
from sentinel_hl.services.wol import WolService

__all__ = ['HostService', 'HostUpdatePrereqError']

class HostUpdatePrereqError(Exception):
    pass 

class HostService:
    def __init__(self, host: HostModel, policy: HostsPolicyModel, *, datastore: Datastore, wol: WolService, logger: logging.Logger):
        self._host: HostModel = host
        self._policy: HostsPolicyModel = policy

        self._datastore: Datastore = datastore
        self._wol: WolService = wol
        self._logger: logging.Logger = logger
        
        self._cache: dict = self._datastore.get(self._host.name, {})
        self._cache_ip: bool = bool(not self._host.ip)
        self._cache_mac: bool = bool(not self._host.mac)
        
        self._wake_locked: list[str] = []
        self._wake_in_progress: bool = False
        self._shutdown_in_progress: bool = False

    @property
    def name(self) -> str:
        return self._host.name
    
    @property
    def hostname(self) -> str:
        return self._host.hostname
    
    @property
    def ip(self) -> str:
        return self._host.ip
    
    @property
    def mac(self) -> str:
        return self._host.mac
    
    @property
    def status(self) -> str | None:
        return self._cache.get('status')
    
    async def check(self) -> None:
        self._logger.debug(f'Checking host "{self.name}"...')
        
        if not self._host.ip or not self._host.mac:
            self._logger.warning(f'IP or MAC not discovered properly for "{self._host.name}". Skipping check')
            return
        
        if self._wake_in_progress or self._shutdown_in_progress:
            self._logger.debug(f'Host "{self._host.name}" is currently in wake or shutdown operation. Skipping check')
            return
        
        await self._check_status()
        
        if self.status == 'up':
            self._logger.debug(f'Host "{self._host.name}" is up')
        else:
            self._logger.info(f'Host "{self._host.name}" is down. Attempting to wake it up')
            
            try:
                await self.wake()
            except Exception as e:
                self._logger.error(f'Failed to wake host "{self._host.name}": {e}')

    async def discover(self) -> None:
        if self._cache_ip and self._host.hostname:
            if self._cache.get('ip_expiry', 0) <= asyncio.get_event_loop().time():
                self._logger.info(f'Attempting to fetch IP address for "{self._host.name}" by hostname "{self._host.hostname}"...')

                try:
                    ip = await HostDiscovery.get_ip_by_hostname(self._host.hostname)
                    
                    self._logger.info(f'Found IP address {ip} for "{self._host.name}"')

                    self._cache['ip'] = ip
                    self._cache['ip_expiry'] = asyncio.get_event_loop().time() + self._policy.ip_cache_ttl
                except Exception as e:
                    self._logger.error(f'Failed to resolve IP for "{self._host.name}" by hostname "{self._host.hostname}": {e}')
                    
            else:
                self._logger.debug(f'Using IP address {self._cache["ip"]} from cache for "{self._host.name}"')
                    
            self._host.ip = self._cache.get('ip', '')
                            
        if self._cache_mac and self._host.ip:
            if self._cache.get('mac_expiry', 0) <= asyncio.get_event_loop().time():
                self._logger.info(f'Attempting to fetch MAC address for "{self._host.name}" by IP address "{self._host.ip}"...')

                try:
                    mac = await HostDiscovery.get_mac_by_ip(self._host.ip)

                    self._logger.info(f'Found MAC address {mac} for "{self._host.name}"')

                    self._cache['mac'] = mac
                    self._cache['mac_expiry'] = asyncio.get_event_loop().time() + self._policy.mac_cache_ttl
                except Exception as e:
                    self._logger.error(f'Failed to resolve MAC for "{self._host.name}" by IP address "{self._host.ip}": {e}')

            else:
                self._logger.debug(f'Using MAC address {self._cache["mac"]} from cache for "{self._host.name}"')

            self._host.mac = self._cache.get('mac', '')
        
        self._persist_cache()

        self._logger.debug(f'Host details for "{self._host.name}": IP={self._host.ip}, MAC={self._host.mac}')
        
    async def wake(self) -> None:
        if self._wake_in_progress:
            raise HostUpdatePrereqError(f'Wake operation for host is already in progress')

        if self.status is None or self.status == 'up':
            raise HostUpdatePrereqError(f'Invalid host status ({self.status}). Skipping wake')

        # check if locked
        if self._wake_locked:
            raise HostUpdatePrereqError(f'Host is locked: {self._wake_locked}')
        
        # check if in backoff period
        if self._cache.get('wake_backoff', 0) > asyncio.get_event_loop().time():
            raise HostUpdatePrereqError(f'Host is in backoff')

        self._logger.info(f'Waking up host "{self._host.name}" via Wake-on-LAN ...')

        # try to wake the host up using Wake-on-LAN
        self._wol.wake_host(self._host)
        self._logger.debug(f'Wake-on-LAN packet sent to {self._host.mac}')
        
        asyncio.create_task(self._poll_wake())
    
    async def shutdown(self) -> None:
        if self._shutdown_in_progress:
            raise HostUpdatePrereqError(f'Shutdown operation is already in progress')
        
        if self.status is None or self.status == 'down':
            raise HostUpdatePrereqError(f'Invalid host status ({self.status}). Skipping shutdown')

        self._logger.info(f'Shutting down host "{self._host.name}" ...')

        await CmdExec.exec(['shutdown', 'now'], host=CmdExecHost(host=self._host.ip))

        asyncio.create_task(self._poll_shutdown())

    def lock_wake(self, token: str) -> None:
        self._wake_locked.append(token)

    def unlock_wake(self, token: str) -> None:
        self._wake_locked.remove(token)

    def _persist_cache(self) -> None:
        if not self._cache:
            self._logger.debug(f'No cache data for host to write')
            return
        
        self._datastore.set(self._host.name, self._cache)
        
        self._logger.debug(f'Cache data for host persisted')
        
    async def _check_status(self) -> None:
        # ping the host to check if it's reachable
        try:
            await CmdExec.ping(self._host.ip, count=1, timeout=5)
            self._cache['status'] = 'up'
        except CmdExecProcessError as e:
            self._cache['status'] = 'down'
            
        self._persist_cache()

    async def _poll_wake(self) -> None:
        self._wake_in_progress = True
            
        updated = False
        
        self._logger.debug(f'Polling host "{self._host.name}" status after wake action...')

        for _ in range(self._policy.status_poll_retry):
            # sleep for a while to allow the host to respond
            await asyncio.sleep(15)
            
            await self._check_status()
            
            if self.status == 'up':
                updated = True   
                self._logger.info(f'Host "{self._host.name}" confirmed up after wake')
                break
            
        self._wake_in_progress = False
            
        if not updated:            
            self._cache['wake_backoff'] = asyncio.get_event_loop().time() + self._policy.wake_backoff
            self._persist_cache()

            self._logger.warning(f'Host "{self._host.name}" did not confirm status after wake action. Considering it still down and backing off for {self._policy.wake_backoff}s')

    async def _poll_shutdown(self) -> None:
        self._shutdown_in_progress = True

        updated = False
        
        self._logger.debug(f'Polling host "{self._host.name}" status after shutdown action...')

        for _ in range(self._policy.status_poll_retry):
            # sleep for a while to allow the host to respond
            await asyncio.sleep(15)
            
            await self._check_status()
            
            if self.status == 'down':
                updated = True
                self._logger.info(f'Host "{self._host.name}" confirmed down after shutdown')
                break
            
        self._shutdown_in_progress = False
            
        if not updated:
            self._logger.error(f'Host "{self._host.name}" did not confirm status after shutdown action. Considering it still up')