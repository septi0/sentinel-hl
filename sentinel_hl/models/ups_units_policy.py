from enum import auto
from pydantic import BaseModel, ConfigDict, Field
from typing import Union, Literal

class UpsUnitsPolicyModel(BaseModel):
    wake_cooldown: int = Field(default=120, ge=0)
    shutdown_threshold: Union[Literal['auto'], int] = 'auto'

    model_config = ConfigDict(extra='forbid')