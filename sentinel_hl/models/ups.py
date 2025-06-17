from pydantic import BaseModel, ConfigDict

class UpsModel(BaseModel):
    name: str
    nut_id: str
    nut_host: str
    nut_port: int
    hosts: list[str]

    model_config = ConfigDict(extra='forbid')