class GracefulExit(SystemExit):
    code = 1

class SentinelHlRuntimeError(Exception):
    pass