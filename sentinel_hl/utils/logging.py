import logging

class NoExceptionFormatter(logging.Formatter):
    def format(self, record):
        exc_info = record.exc_info
        record.exc_info = None
        
        formatted = super().format(record)
        
        record.exc_info = exc_info
        
        return formatted

class DebugLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

    def error(self, msg, *args, **kwargs):
        kwargs.setdefault('exc_info', True)
        super().error(msg, *args, **kwargs)