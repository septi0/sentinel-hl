import logging
import socket
import re
from sentinel_hl.libraries.cmd_exec import CmdExec

class HostDiscovery:
    @classmethod
    async def get_ip_by_hostname(cls, hostname: str) -> str:
        ip = socket.gethostbyname(hostname)
            
        return ip

    @classmethod
    async def get_mac_by_ip(cls, ip: str) -> str:
        await CmdExec.ping(ip, count=1, timeout=5)

        # get MAC information from the neighbor table
        arp_result = await CmdExec.exec(['ip', 'neighbor', 'show', ip])
        
        # parse the output to extract the MAC address
        mac = re.search(r'([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})', arp_result)
        
        if mac:
            mac = mac.group(0).upper()
        else:
            logging.error(f"MAC address not found in neighbor table for '{ip}': {arp_result}")
            return ''

        return mac