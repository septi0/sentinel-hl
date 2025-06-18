import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

class UpsUnitsPolicyModel(BaseModel):
    wake_cooldown: int = Field(default=120, ge=0)
    shutdown_threshold: int = Field(default=30, ge=0)
    shutdown_threshold_unit: Literal['%', 's'] = '%'

    model_config = ConfigDict(extra='forbid')
    
    @model_validator(mode='before')
    @classmethod
    def validate_before(cls, values):
        pattern = r'^(\d+)([%|s])?$'

        if values.get('shutdown_threshold'):
            match = re.match(pattern, str(values['shutdown_threshold']))

            if not match:
                raise ValueError('Invalid shutdown_threshold provided')
            
            if match.group(2) and values.get('shutdown_threshold_unit') and match.group(2) != values['shutdown_threshold_unit']:
                raise ValueError('shutdown_threshold_unit conflict')
            
            values['shutdown_threshold'] = match.group(1)
            if match.group(2): values['shutdown_threshold_unit'] = match.group(2)
        
        return values
    
    @model_validator(mode='after')
    @classmethod
    def validate_after(cls, values):
        if values.shutdown_threshold_unit == '%':
            if not (0 <= int(values.shutdown_threshold) <= 100):
                raise ValueError('shutdown_threshold must be between 0 and 100 when using % unit')
            
        return values