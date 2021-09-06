from api import logger, CommandReturnCode, Cmdline, Command, CommandType, Session
import argparse
import os
import json
import re
import base64

class RmCommand(Command):
    description = "删除远程服务器上的文件或目录"
    command_name = 'rm'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('dest', help="远程文件或目录路径.", nargs='+')
        self.parse.add_argument('-f', '--force', help="不加询问的删除文件.", action='store_true')
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.force or input("确定要删除这些文件吗?(y/n) ").lower() == 'y':
            flist = "\n".join(args.dest)
            ret = self.session.evalfile('payload', dict(flist=flist, pwd=self.session.server_info.pwd))
            if ret is None:
                logger.error("删除文件发生错误!")
                return CommandReturnCode.FAIL
            ret = json.loads(ret)
            for msg in ret['msg']:
                msg = base64.b64decode(msg).decode(self.session.options.get_option('encoding').value, 'ignore')
                if 'failed' in msg or 'exist' in msg:
                    logger.warning(msg)
                else:
                    logger.info(msg)
            if ret['code'] == -1:
                return CommandReturnCode.FAIL

        return CommandReturnCode.SUCCESS
