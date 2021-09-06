import argparse
import os
import re

from api import Command, Cmdline, CommandReturnCode, CommandType, Session, logger

class CpCommand(Command):
    description = "复制文件"
    command_name = 'cp'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('source_path', help="远程文件源路径.")
        self.parse.add_argument('dest_path', help="远程文件目的路径.")
        self.help_info = self.parse.format_help()
        self.session = session


    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        result = self.session.evalfile('payload', dict(pwd=self.session.server_info.pwd, source=args.source_path, 
            dest=args.dest_path, f=False)).strip()
        if result is None:
            logger.error("文件复制错误!")
            return CommandReturnCode.FAIL
        
        if result == b'Dest file exists':
            if input(f"目标文件存在，是否覆盖?(y/n) ").lower() == 'y':
                result = self.session.evalfile('payload', dict(pwd=self.session.server_info.pwd, source=args.source_path, 
                    dest=args.dest_path, f=True)).strip()
            else:
                return CommandReturnCode.CANCEL
                
        if result == b'ok':
            logger.info(f"复制`{args.source_path}`到`{args.dest_path}`成功!")
            return CommandReturnCode.SUCCESS
        else:
            print(result.decode(self.session.options.get_option('encoding').value, errors='ignore'))
            logger.error(f"复制`{args.source_path}`到`{args.dest_path}`失败！权限不足！")
            return CommandReturnCode.FAIL