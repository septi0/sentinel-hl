import sys
import os
import argparse
from pydantic import ValidationError
from sentinel_hl.manager import SentinelHlManager
from sentinel_hl.exceptions import SentinelHlRuntimeError
from sentinel_hl.info import __app_name__, __description__, __author__, __author_email__, __author_url__, __license__

__version__ = ''
with open(os.path.join(os.path.dirname(__file__), 'VERSION'), 'r') as f:
    __version__ = f.read().strip()

def main():
    # get args from command line
    parser = argparse.ArgumentParser(description=__description__)
    
    parser.add_argument('--config', dest='config_file', help='Alternative config file')
    parser.add_argument('--log', dest='log_file', help='Log file where to write logs')
    parser.add_argument('--log-level', dest='log_level', help='Log level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('--version', action='version', version=f'{__app_name__} {__version__}')

    subparsers = parser.add_subparsers(title="Commands", dest="command")
    
    daemon_parser = subparsers.add_parser('daemon', help='Run as daemon')
    
    daemon_reload_parser = subparsers.add_parser('daemon-reload', help='Reload running daemon')
    
    clear_caches_parser = subparsers.add_parser('clear-cache', help='Clear cache')

    ack_parser = subparsers.add_parser('ack', help='Acknowledge host down')
    ack_parser.add_argument('host', nargs=1, help='Host to acknowledge down')

    clear_ack_parser = subparsers.add_parser('clear-ack', help='Clear acknowledged host')
    clear_ack_parser.add_argument('host', nargs=1, help='Host to clear acknowledgment')

    args = parser.parse_args()
    
    try:
        sentinel_hl = SentinelHlManager(log_file=args.log_file, log_level=args.log_level, config_file=args.config_file)
    except ValidationError as e:
        print(f"Configuration file contains {e.error_count()} error(s):")
        
        for error in e.errors(include_url=False):
            loc = '.'.join(str(x) for x in error['loc']) if error['loc'] else 'general'
            print(f"  - {loc}: {error['msg']}")
            exit()

        print(f"\nCheck documentation for more information on how to configure Sentinel-Hl")
        sys.exit(2)
    
    if args.command == 'daemon':
        sentinel_hl.run_forever()
    elif args.command == 'daemon-reload':
        sentinel_hl.reload()
    elif args.command == 'clear-cache':
        sentinel_hl.clear_cache()
    elif args.command == 'ack':
        sentinel_hl.ack_host(args.host[0])
    elif args.command == 'clear-ack':
        sentinel_hl.ack_host(args.host[0], clear=True)
    elif args.command is None:
        sentinel_hl.run_once()

    sys.exit(0)