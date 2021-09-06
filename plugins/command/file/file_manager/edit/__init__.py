from api import logger, CommandReturnCode, Cmdline, Command, CommandType, Session
import argparse
import base64
import tempfile
import os
import json

class EditCommand(Command):
    description = "编辑远程文件内容"
    command_name = 'edit'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('source_path', help="远程文件路径.")
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        logger.info('下载文件...')
        source_path = args.source_path
        data = self.session.evalfile('download', dict(path=source_path, pwd=self.session.server_info.pwd))
        if data is None:
            logger.error("文件下载错误!")
            return CommandReturnCode.FAIL
        data = json.loads(data)
        if data['code'] == 0:
            logger.error(f"服务器文件`{source_path}`不存在！")
            return CommandReturnCode.FAIL
        elif data['code'] == -1:
            logger.error(f"文件不可读！权限不足！")
            return CommandReturnCode.FAIL
        elif data['code'] == -2:
            logger.error(f"文件不可写！权限不足！")
            return CommandReturnCode.FAIL
        else:
            logger.info('文件下载成功!')
        data = base64.b64decode(data['msg'].encode())
        fname = source_path.replace('/', '_').replace('\\', '_')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, fname)
            with open(path, 'wb') as f:
                f.write(data)
            editor = self.session.options.get_option('editor').value
            if os.system(f"{editor} {path}") != 0:
                logger.error(f"运行编辑器`{editor}`失败!编辑器必须可通过`editor filepath`的方式打开文件。")
                logger.info(f"你能使用set命令来设置当前使用的编辑器！")
                return CommandReturnCode.FAIL

            ret = b''
            # 检查是否有改动
            with open(path, 'rb') as f:
                ret = f.read()
                if ret == data:
                    logger.warning('文件内容无改变！')
                    return CommandReturnCode.CANCEL
            #应用更改
            if input("确定保存修改吗？(y/n)").lower() != 'y':
                return CommandReturnCode.CANCEL
            logger.info("文件上传...")
            ret = self.session.evalfile('upload', dict(data=ret, path=source_path, pwd=self.session.server_info.pwd))
            if ret is None:
                logger.error("文件上传错误!")
                return CommandReturnCode.FAIL
            if ret == b'1':
                logger.info(f"文件`{source_path}`编辑成功!")
                return CommandReturnCode.SUCCESS
            elif ret == b'-1':
                logger.error(' 文件写入不完整！请再次尝试！')
            else:
                logger.error("文件上传发生了未知错误!")
        
        return CommandReturnCode.FAIL
        