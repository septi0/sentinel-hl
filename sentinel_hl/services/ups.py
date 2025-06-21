import asyncio
import logging
from sentinel_hl.libraries.datastore import Datastore
from sentinel_hl.libraries.nut import Nut
from sentinel_hl.models.ups import UpsModel
from sentinel_hl.models.ups_units_policy import UpsUnitsPolicyModel
from sentinel_hl.services.host import HostService

__all__ = ['UpsService']

class UpsService:
    def __init__(self, ups: UpsModel, hosts: list[HostService], policy: UpsUnitsPolicyModel, *, datastore: Datastore, logger: logging.Logger):
        self._ups: UpsModel = ups
        self._hosts: list[HostService] = hosts
        self._policy: UpsUnitsPolicyModel = policy

        self._datastore: Datastore = datastore
        self._logger: logging.Logger = logger
        
        self._nut: Nut = Nut(ups.nut_host, ups.nut_port, logger=logger)
        self._cache: dict = self._datastore.get(self._ups.name, {})
        
        self._wake_cooldown: float | None = None
        self._last_status: str | None = None
    
    @property
    def name(self) -> str:
        return self._ups.name    
    
    @property
    def connected(self) -> bool:
        return self._nut.connected

    async def poll(self) -> None:
        try:
            ups_data = await self._nut.get_ups_vars(self._ups.nut_id)
        except Exception as e:
            self._logger.error(f'Error polling UPS "{self._ups.name}": {e}')
            return
        
        if not ups_data:
            return
        
        if 'OL' in ups_data['ups.status']: await self._handle_online_status(ups_data)
        elif 'OB' in ups_data['ups.status']: await self._handle_onbatt_status(ups_data)
            
        return
    
    async def disconnect(self) -> None:
        await self._nut.disconnect()

    async def _handle_online_status(self, ups_data: dict) -> None:
        if self._last_status == 'OB':
            self._logger.info(f'UPS "{self._ups.name}" is back online')
            
        self._last_status = 'OL'
        
        if self._cache.get('onbatt'):
            # unset on battery info if UPS is back online
            self._cache['onbatt'] = None
            self._persist_cache()

        if not self._cache.get('hosts_halted'):
            return
        
        if not self._wake_cooldown:
            self._wake_cooldown = asyncio.get_event_loop().time() + self._policy.wake_cooldown
            self._logger.info(f'Waking up hosts after UPS is stable for {self._policy.wake_cooldown}s')
            return

        if self._wake_cooldown > asyncio.get_event_loop().time():
            self._logger.debug(f'UPS "{self._ups.name}" is in cooldown period')
            return
        
        self._wake_cooldown = None
            
        self._cache['hosts_halted'] = False
        self._persist_cache()
        self._logger.info(f'UPS "{self._ups.name}" was stable for {self._policy.wake_cooldown}s. Waking hosts')

        for host in self._hosts:
            try:
                host.unlock_wake(self._ups.name)
                await host.wake()
            except Exception as e:
                self._logger.error(f'Could not wake host "{host.name}": {e}')
    
    async def _handle_onbatt_status(self, ups_data: dict) -> None:
        if self._last_status == 'OL':
            self._logger.info(f'UPS "{self._ups.name}" has switched to battery power')
        
        self._last_status = 'OB'
            
        if self._wake_cooldown:
            # unset wake cooldown if UPS is on battery
            self._wake_cooldown = None
            return
        
        if self._cache.get('hosts_halted'):
            return
        
        if self._policy.shutdown_threshold_unit == 's':
            # process shutdown based on time left
            if not self._cache.get('onbatt'):
                self._cache['onbatt'] = (asyncio.get_event_loop().time(), ups_data.get('battery.charge', 0))
                self._persist_cache()
                
            current = self._get_battery_time_left(ups_data)
            
            if current is None or current > self._policy.shutdown_threshold:
                return
        elif self._policy.shutdown_threshold_unit == '%':
            # process shutdown based on battery percentage
            current = ups_data.get('battery.charge', 0)
            
            if current > self._policy.shutdown_threshold:
                return

        self._logger.warning(f'UPS "{self._ups.name}" is on battery and below shutdown threshold {self._policy.shutdown_threshold}{self._policy.shutdown_threshold_unit} ({current}{self._policy.shutdown_threshold_unit}). Initiating shutdown')

        for host in self._hosts:
            # skip hosts that are already down
            if host.status == 'down':
                continue
            
            try:
                # try to shut down the host
                await host.shutdown()
                host.lock_wake(self._ups.name)
            except Exception as e:
                self._logger.error(f'Error shutting down host "{host.name}": {e}')

        self._cache['hosts_halted'] = True
        self._persist_cache()
    
    def _persist_cache(self) -> None:
        if not self._cache:
            self._logger.debug(f'No cache data for UPS "{self._ups.name}" to write')
            return

        self._datastore.set(self._ups.name, self._cache)

        self._logger.debug(f'Cache data for UPS "{self._ups.name}" persisted')
        
    def _get_battery_time_left(self, ups_data: dict) -> float | None:
        onbatt_time, onbatt_charge = self._cache.get('onbatt', (0, 0))

        elapsed = asyncio.get_event_loop().time() - onbatt_time
        charge_used = onbatt_charge - ups_data.get('battery.charge', 0)
        
        if charge_used <= 0 or elapsed <= 0:
            return None
        
        # Calculate time left based on charge used and elapsed time
        drain_rate = charge_used / elapsed
        
        if drain_rate <= 0:
            return None
        
        return round(ups_data.get('battery.charge', 0) / drain_rate, 2)
    
    def __str__(self) -> str:
        return self.name