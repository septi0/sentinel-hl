from pydantic import BaseModel, ConfigDict, Field

class HostsPolicyModel(BaseModel):
    status_poll_retry: int = Field(default=3, ge=1)
    wake_backoff: int = Field(default=600, ge=0)
    ip_cache_ttl: int = Field(default=3600, ge=0)
    mac_cache_ttl: int = Field(default=3600, ge=0)

    model_config = ConfigDict(extra='forbid')