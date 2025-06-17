from pydantic import BaseModel, ConfigDict

class EmailNotifyModel(BaseModel):
    sender: str
    to: list[str]
    smtp_server: str
    smtp_server_port: int = 25
    use_tls: bool = False
    use_ssl: bool = False
    username: str = ''
    password: str = ''

    model_config = ConfigDict(extra='forbid')