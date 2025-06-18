from pydantic import BaseModel, ConfigDict, Field, model_validator
from sentinel_hl.models.host import HostModel
from sentinel_hl.models.hosts_policy import HostsPolicyModel
from sentinel_hl.models.ups import UpsModel
from sentinel_hl.models.ups_units_policy import UpsUnitsPolicyModel
from sentinel_hl.models.wol import WolModel

class SentinelHlModel(BaseModel):
    hosts: list[HostModel] = []
    hosts_policy: HostsPolicyModel = HostsPolicyModel()
    ups: list[UpsModel] = []
    ups_units_policy: UpsUnitsPolicyModel = UpsUnitsPolicyModel()
    wol: WolModel = WolModel()
    ups_poll_interval: int = Field(default=10, ge=5)
    hosts_check_interval: int = Field(default=60, ge=30)

    model_config = ConfigDict(extra='forbid')
    
    @model_validator(mode='after')
    @classmethod
    def validate_after(cls, values):
        # ensure that hosts[].name is unique
        host_names = [host.name for host in values.hosts]
        if len(host_names) != len(set(host_names)):
            raise ValueError('Host names must be unique')

        # ensure that ups[].name is unique
        ups_names = [ups.name for ups in values.ups]
        if len(ups_names) != len(set(ups_names)):
            raise ValueError('UPS names must be unique')
            
        return values