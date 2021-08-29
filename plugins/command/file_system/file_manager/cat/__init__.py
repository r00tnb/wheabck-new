
from api import logger, Command, Session, Cmdline, CommandReturnCode, CommandType
import argparse
import base64
import tempfile
import os
import json

class CatCommand(Command):
    description = '查看文件内容'

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog="cat", description=self.description)
        self.parse.add_argument('remote', help="远程文件路径.")
        self.parse.add_argument('-v', '--view', help="在编辑器中显示文件内容.", action='store_true')
        self.help_info = self.parse.format_help()
        self.session = session

    @property
    def command_name(self) -> str:
        return 'cat'

    @property
    def command_type(self) -> CommandType:
        return CommandType.FILE_COMMAND

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        ret = self.session.evalfile('cat', dict(pwd=self.session.server_info.pwd, path=args.remote))
        if ret is None:
            logger.error("文件读取错误!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 0:
            logger.error("远程文件路径不存在!")
        elif ret['code'] == -1:
            logger.error("远程文件不可读，权限不足！")
        elif ret['code'] == 1:
            data = base64.b64decode(ret['msg'].encode())
            if args.view:# 在编辑器中显示
                fname = args.remote.replace('/', '_').replace('\\', '_')
                with tempfile.TemporaryDirectory() as tmpdir:
                    path = os.path.join(tmpdir, fname)
                    with open(path, 'wb') as f:
                        f.write(data)
                    editor = self.session.options.get_option('editor')
                    logger.info(f"在编辑器`{editor}`中展示文件内容.")
                    if os.system(f"{editor} {path}") != 0:
                        logger.error(f"运行编辑器`{editor}`失败!编辑器必须可通过`editor filepath`的方式打开文件。")
                        logger.info(f"你能使用set命令来设置当前使用的编辑器！")
                        return CommandReturnCode.FAIL
            else:
                data = data.decode(self.session.options.get_option('encoding'), 'ignore')
                print(data)
            return CommandReturnCode.SUCCESS
        return CommandReturnCode.FAIL