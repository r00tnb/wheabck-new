from api import logger, Session, CommandReturnCode, Command, CommandType, Cmdline
import argparse
import os
import json
import re
import base64
import time

class TouchCommand(Command):
    description = "修改远程服务器文件的访问时间、修改时间，文件不存在则创建空文件"
    command_name = 'touch'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('dest', help="远程服务器文件路径.")
        pa = self.parse.add_mutually_exclusive_group()
        pa.add_argument('-a', '--access', help="指定文件最后的访问时间(类似1997-01-18 14:55:32).", 
            type=self._check)
        pa.add_argument('-A', '--access-timestamp', help="指定文件最后的访问时间戳", type=int)

        pm = self.parse.add_mutually_exclusive_group()
        pm.add_argument('-m', '--modify', help="指定文件最后的修改时间(类似1997-01-18 14:55:32).", 
            type=self._check)
        pm.add_argument('-M', '--modify-timestamp', help="指定文件最后的修改时间戳", type=int)
        self.help_info = self.parse.format_help()
        self.session = session

    def _check(self, param: str)-> int:
        try:
            timestamp = time.mktime(time.strptime(param, "%Y-%m-%d %H:%M:%S"))
            return int(timestamp)
        except Exception:
            raise ValueError(f"错误的时间格式`{param}`!")

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        ret = self.session.evalfile('payload', dict(file=args.dest, atime=args.access, mtime=args.modify, pwd=self.session.server_info.pwd))
        if ret is None:
            logger.error("Touch文件错误!")
            return self.STOP
        if ret == b'1':
            logger.info(f'Touch文件`{args.dest}`成功！')
        else:
            logger.error(f'Touch文件`{args.dest}`失败！')
            return CommandReturnCode.FAIL
        return CommandReturnCode.SUCCESS
