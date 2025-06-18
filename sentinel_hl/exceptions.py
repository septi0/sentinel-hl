class ExitSignal(SystemExit):
    code = 1
    
class SIGHUPSignal(SystemExit):
    code = 2
    
class SentinelHlRuntimeError(Exception):
    pass