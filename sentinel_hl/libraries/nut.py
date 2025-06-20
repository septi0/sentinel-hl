import logging
import asyncio
import re
from typing import Optional

__all__ = ['Nut']

class NutError(Exception):
    pass

class Nut:
    def __init__(self, host: str, port: int, *, logger: Optional[logging.Logger] = None):
        self._host: str = host
        self._port: int = port

        self._logger: logging.Logger = logger or logging.getLogger(__name__)
        
        self._connect_timeout: int = 2
        self._write_timeout: int = 2
        self._read_timeout: int = 2
        
        self._writer: asyncio.StreamWriter | None = None
        self._reader: asyncio.StreamReader | None = None
        self._connected: bool = False
        self._initialized: bool = False
        
    @property
    def connected(self) -> bool:
        return self._connected and self._writer is not None and self._reader is not None and not self._writer.is_closing()
        
    async def get_ups_vars(self, ups_id: str) -> dict | None:
        if not ups_id:
            raise ValueError('UPS ID must be provided')
        
        data = await self.communicate(f'LIST VAR {ups_id}')
        
        if not data:
            self._logger.warning(f'No data received for UPS ID {ups_id}')
            return None

        pattern = fr'VAR {ups_id} (\S+) "(.+?)"'
        
        vars = {
            match.group(1): match.group(2)
            for match in re.finditer(pattern, data)
        }

        cast_float = ['battery.charge', 'battery.voltage', 'battery.voltage.high', 'battery.voltage.low', 'input.voltage', 'output.voltage']

        for key in cast_float:
            vars[key] = float(vars.get(key, 0))
        
        vars['ups.status'] = vars.get('ups.status', '').split(' ')
        
        return vars

    async def communicate(self, command: str) -> str | None:
        # Ensure we have a valid connection
        if not await self._ensure_connection():
            raise ConnectionError(f'Could not connect to UPS at {self._host}:{self._port}')
        
        if not command:
            raise ValueError('Command cannot be empty')
        
        self._logger.debug(f'UPS {self._host}:{self._port} sending command: {command}')
            
        try:
            # Send command with timeout
            command_bytes = f'{command}\n'.encode('utf-8')
            self._writer.write(command_bytes) # type: ignore
            await asyncio.wait_for(self._writer.drain(), timeout=self._write_timeout) # type: ignore
            
            beginning = await self._readline()
            
            if beginning.startswith('ERR '):
                raise NutError(beginning.replace('ERR ', '', 1).strip())
            
            if beginning != f"BEGIN {command}":
                raise NutError('Unknown response from UPS: ' + beginning)
            
            data = ''
            
            while True:
                line = await self._readline()
                
                if line == f"END {command}":
                    break
                
                data += line + '\n'

            return data.strip()

        except asyncio.TimeoutError:
            self._logger.warning(f'UPS {self._host}:{self._port}: Timeout during polling')
            # Don't disconnect on timeout - connection might still be valid
            return None
            
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            self._logger.warning(f'UPS {self._host}:{self._port}: Connection error during poll: {e}')
            await self.disconnect()
            return None
            
        except OSError as e:
            self._logger.error(f'UPS {self._host}:{self._port}: Network error during poll: {e}')
            await self.disconnect()
            return None
            
        except UnicodeDecodeError as e:
            self._logger.error(f'UPS {self._host}:{self._port}: Invalid response encoding: {e}')
            # Don't disconnect - this might be a temporary issue
            return None
        
        except EOFError as e:
            self._logger.error(f'UPS {self._host}:{self._port}: EOFError during poll: {e}')
            # Disconnect on EOF to reset the connection
            await self.disconnect()
            return None
        
        except NutError:
            # Let NutError propagate to the caller
            raise
            
        except Exception as e:
            self._logger.error(f'UPS {self._host}:{self._port}: Unexpected error during poll: {e}')
            # For unexpected errors, disconnect to be safe
            await self.disconnect()
            return None
    
    async def _ensure_connection(self) -> bool:
        if self.connected:
            return True
            
        return await self._connect()
    
    async def _connect(self) -> bool:
        if self._initialized:
            await self.disconnect()
            
        self._initialized = True

        try:
            # Attempt to open connection with a timeout
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._connect_timeout
            )
            
            self._connected = True
            self._logger.info(f'UPS connection at {self._host}:{self._port} established')
            return True
            
        except asyncio.TimeoutError:
            self._logger.error(f'UPS {self._host}:{self._port}: Connection timeout')
            await self.disconnect()
            return False
            
        except OSError as e:
            self._logger.error(f'UPS {self._host}:{self._port}: Failed to connect: {e}')
            await self.disconnect()
            return False
            
        except Exception as e:
            self._logger.error(f'UPS {self._host}:{self._port}: Unexpected connection error: {e}')
            await self.disconnect()
            return False
    
    async def disconnect(self) -> None:
        self._connected = False
        
        if self._writer and not self._writer.is_closing():
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
            except Exception as e:
                self._logger.debug(f'Error during disconnect cleanup: {e}')
        
        self._reader = None
        self._writer = None
        
        self._logger.info(f'Closed UPS connection at {self._host}:{self._port}')
        
    async def _readline(self) -> str:
        line = await asyncio.wait_for(self._reader.readuntil(b"\n"), timeout=self._read_timeout) # type: ignore

        if not line:
            raise EOFError('No data received from UPS')
        
        return line.decode('utf-8').strip()