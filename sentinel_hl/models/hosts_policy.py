from pydantic import BaseModel, ConfigDict, Field

class HostsPolicyModel(BaseModel):
    ack_status_interval: int = Field(default=15, ge=5)
    ack_status_retry: int = Field(default=3, ge=1)
    wake_backoff: int = Field(default=600, ge=0)
    ip_cache_ttl: int = Field(default=3600, ge=0)
    mac_cache_ttl: int = Field(default=3600, ge=0)

    model_config = ConfigDict(extra='forbid')