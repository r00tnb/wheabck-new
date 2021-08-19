from api import logger, colour, Session
import base64
import json

class CmdOnServer:
    def __init__(self, session:Session, method:str):

        self.method = method
        self.session = session
    
    def exec(self, cmdline: bytes)->bytes:
        '''在服务器上执行命令并获取结果
        '''
        raise NotImplementedError()

    @property
    def available_methods(self)->tuple:
        return ()

class PHPCmd(CmdOnServer):

    def exec(self, cmdline: bytes)->bytes:
        '''在服务器上执行命令并获取结果
        '''
        fl = [self.method]
        if self.method in ('auto', None, ''):
            fl = ['exec', 'shell_exec', 'system', 'passthru', 'popen', 'proc_open', 'wscript']
        for f in fl:
            tmp = self.session.evalfile(f'php/{f}', dict(cmd=cmdline, pwd=self.session.server_info.pwd))
            if tmp is None:
                return None
            r = json.loads(tmp)
            if r['code'] == 0:
                continue
            self.method = f
            result = base64.b64decode(r['result'].encode())
            return result

        logger.warning('无法执行系统命令！或许是命令执行函数被禁用')
        return None

    @property
    def available_methods(self)->tuple:
        return ('exec', 'shell_exec', 'system', 'passthru', 'popen', 'proc_open', 'wscript', 'auto')

class CSharpCmd(CmdOnServer):

    def exec(self, cmdline: bytes)->bytes:
        '''在服务器上执行命令并获取结果
        '''
        ret = self.session.evalfile('csharp/exec', dict(pwd=self.exp.session.pwd, cmd=cmdline, shell=self.method))
        if ret is None:
            return None
        ret = json.loads(ret)
        if ret['code'] == 1:
            return base64.b64decode(ret['result'].encode())

        return None

    @property
    def available_methods(self)->tuple:
        return ('shell', 'process')