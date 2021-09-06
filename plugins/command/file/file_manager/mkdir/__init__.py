from api import logger, Session, CommandReturnCode, CommandType, Command, Cmdline
import argparse
import os
import json
import re
import base64

class MkdirCommand(Command):
    description = "在服务器上创建一个目录"
    command_name = 'mkdir'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('dest', help="远程目录路径.")
        self.parse.add_argument('-m', '--mode', help="设置权限模式，类似chmod，指定一个8进制整数", type=lambda x:int(x, 8))
        self.help_info = self.parse.format_help()
        self.session = session


    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        ret = self.session.evalfile('payload', dict(path=args.dest, mode=0o777 if args.mode is None else args.mode, 
            pwd=self.session.server_info.pwd))
        if ret is None:
            logger.error(f'创建目录`{args.dest}`错误 ！')
            return CommandReturnCode.FAIL
        if ret == b'1':
            logger.info(f'创建目录`{args.dest}`成功！')
        else:
            logger.error(f'创建目录`{args.dest}`失败！')
            return CommandReturnCode.FAIL
        return CommandReturnCode.SUCCESS
