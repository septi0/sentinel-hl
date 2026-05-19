from pydantic import BaseModel, ConfigDict, Field, model_validator
from sentinel_hl.models.host import HostModel
from sentinel_hl.models.hosts_policy import HostsPolicyModel
from sentinel_hl.models.ups import UpsModel
from sentinel_hl.models.ups_units_policy import UpsUnitsPolicyModel
from sentinel_hl.models.wol import WolModel

class SentinelHlModel(BaseModel):
    hosts: list[HostModel] = []
    hosts_policy: HostsPolicyModel = Field(default_factory=HostsPolicyModel)
    ups: list[UpsModel] = []
    ups_units_policy: UpsUnitsPolicyModel = Field(default_factory=UpsUnitsPolicyModel)
    wol: WolModel = Field(default_factory=WolModel)
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

        # validate dependencies reference valid hosts and detect cycles
        host_map = {host.name: host for host in values.hosts}
        for host in values.hosts:
            for dep in host.dependencies:
                if dep == host.name:
                    raise ValueError(f'Host "{host.name}" cannot depend on itself')
                if dep not in host_map:
                    raise ValueError(f'Host "{host.name}" has unknown dependency "{dep}"')

        def _has_cycle(name: str, visited: set, path: set) -> bool:
            visited.add(name)
            path.add(name)
            for dep in host_map[name].dependencies:
                if dep not in visited:
                    if _has_cycle(dep, visited, path):
                        return True
                elif dep in path:
                    return True
            path.discard(name)
            return False

        visited: set = set()
        for host_name in host_map:
            if host_name not in visited:
                if _has_cycle(host_name, visited, set()):
                    raise ValueError('Circular dependency detected in hosts configuration')

        return values