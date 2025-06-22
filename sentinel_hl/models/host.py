from pydantic import BaseModel, ConfigDict, model_validator

class HostModel(BaseModel):
    name: str
    hostname: str = ''
    ip: str = ''
    mac: str = ''
    ssh_user: str | None = None
    ssh_port: int | None = None

    model_config = ConfigDict(extra='forbid')
    
    @model_validator(mode='after')
    @classmethod
    def validate_after(cls, values):
        # make sure we have hostname or ip
        if not values.hostname and not values.ip:
            raise ValueError("Either 'hostname' or 'ip' must be provided")

        return values