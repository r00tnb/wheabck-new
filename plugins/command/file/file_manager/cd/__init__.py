
from api import logger, Command, Session, CommandReturnCode, CommandType, Cmdline
import argparse
import os
import re
import json
import base64

class CdCommand(Command):
    description = "切换当前工作目录(不指定路径则输出当前的工作目录路径)"
    command_name = 'cd'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('dir', help="远程目录路径.", nargs='?')
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.dir is not None:
            path = self.session.server_info.pwd
            if args.dir in ('./', '.'):
                return CommandReturnCode.SUCCESS

            ret = self.session.evalfile('payload', dict(pwd=path, path=args.dir))
            if ret is None:
                logger.error("切换当前工作目录错误!")
                return CommandReturnCode.FAIL
            ret = json.loads(ret)
            msg = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
            if ret['code'] == -1:
                logger.error(f"切换目录到`{path}`失败，原因是：{msg}!")
                return CommandReturnCode.FAIL
            elif ret['code'] == 1:
                self.session.server_info.pwd = msg
        else:
            print(self.session.server_info.pwd)
        return CommandReturnCode.SUCCESS