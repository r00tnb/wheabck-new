from api import logger, Session, Cmdline, Command, CommandReturnCode, CommandType
import argparse
import os
import re

class MvCommand(Command):
    description = "移动服务器文件或目录"
    command_name = 'mv'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('sourcepath', help="源路径.")
        self.parse.add_argument("targetpath", help="目的路径.")
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        result = self.session.evalfile('payload', dict(pwd=self.session.server_info.pwd, source=args.sourcepath, 
            dest=args.targetpath, f=False))
        if result is None:
            logger.error("文件或目录移动错误!")
            return CommandReturnCode.FAIL
        
        if result == b'Dest file exists':
            if input("目标文件或目录存在，是否覆盖?(y/n) ").lower() == 'y':
                result = self.session.evalfile('payload', dict(pwd=self.session.server_info.pwd, source=args.sourcepath, 
                    dest=args.targetpath, f=True))
            else:
                return CommandReturnCode.CANCEL
        if result == b'ok':
            logger.info(f"移动`{args.sourcepath}`到`{args.targetpath}`成功!")
            return CommandReturnCode.SUCCESS
        else:
            msg = result.decode(self.session.options.get_option('encoding').value, errors='ignore')
            logger.error(f"移动`{args.sourcepath}`到`{args.targetpath}`失败，原因是: {msg}")
        return CommandReturnCode.FAIL