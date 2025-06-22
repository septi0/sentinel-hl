import logging
import asyncio
import shlex

__all__ = ['CmdExec', 'CmdExecHost', 'CmdExecError', 'CmdExecProcessError']

class CmdExecError(Exception):
    pass

class CmdExecProcessError(Exception):
    def __init__(self, message: str, code: int | None = 0):
        super().__init__(message)
        self.code = code
        
class CmdExecHost:
    def __init__(self, host: str, port: int | None = None, user: str | None = None):
        self._host: str = host
        self._port: int | None = port
        self._user: str | None = user

    @property
    def host(self) -> str:
        return self._host
    
    @property
    def port(self) -> int  | None:
        return self._port
    
    @property
    def user(self) -> str | None:
        return self._user
        
    def __repr__(self):
        return f'CmdExecHost(host={self.host}, port={self.port}, user={self.user})'

class CmdExec:
    @classmethod
    async def exec(cls, cmd: list, *, host: CmdExecHost | None = None, input: str = '', env=None, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE) -> str:
        if host:
            cmd = cls._gen_ssh_cmd(cmd, host)
        
        logging.debug(f'Executing command: {[*cmd]}')
        
        if not env:
            env = None

        process = await asyncio.create_subprocess_exec(*cmd, stdin=stdin, stdout=stdout, stderr=stderr, env=env)

        if input and process.stdin is not None:
            process.stdin.write(input.encode('utf-8'))
            process.stdin.close()

        out, err = await process.communicate()
        
        if process.returncode != 0:
            raise CmdExecProcessError(err.decode('utf-8').strip(), process.returncode)

        result = ''

        if out:
            result = out.decode('utf-8').strip()
        
        return result
    
    @classmethod
    async def ping(cls, host: str, count: int = 3, timeout: int = 5) -> None:
        await cls.exec(['ping', '-c', str(count), '-W', str(timeout), host])
        
    @classmethod
    def _gen_ssh_cmd(cls, cmd: list, host: CmdExecHost) -> list:
        if not cmd or not host:
            raise CmdExecError("Command or host not specified")

        ssh_opts = ['-o', 'PasswordAuthentication=No', '-o', 'BatchMode=yes']

        if host.port is not None:
            ssh_opts += ['-p', str(host.port)]

        remote = host.host
        
        if host.user is not None:
            remote = f"{host.user}@{remote}"

        return ['ssh', *ssh_opts, remote, 'exec', shlex.join(cmd)]