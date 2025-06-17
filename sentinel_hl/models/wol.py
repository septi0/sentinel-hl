from pydantic import BaseModel, ConfigDict

class WolModel(BaseModel):
    port: int = 9
    broadcast: str = '255.255.255.255'

    model_config = ConfigDict(extra='forbid')