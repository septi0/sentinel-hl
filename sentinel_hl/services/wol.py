import logging
from wakeonlan import send_magic_packet
from sentinel_hl.models.wol import WolModel
from sentinel_hl.models.host import HostModel

__all__ = ['WolService']

class WolService:
    def __init__(self, config: WolModel, *, logger: logging.Logger):
        self._config: WolModel = config
        
        self._logger: logging.Logger = logger
        
    def wake_host(self, host: HostModel) -> None:
        if not host.mac:
            self._logger.warning(f'Host "{host.name}" does not have a MAC address configured. Cannot wake.')
            return
        
        send_magic_packet(host.mac, ip_address=self._config.broadcast, port=self._config.port)