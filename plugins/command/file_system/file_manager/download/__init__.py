from api import logger, Session, Cmdline, CommandReturnCode, Command, CommandType, colour
import argparse
import base64
import tempfile
import os
import json


class DownloadCommand(Command):
    description = "下载指定的文件或目录"

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog="download", description=self.description)
        self.parse.add_argument('source_path', help="远程文件或目录路径.")
        self.parse.add_argument('local_path', help="本地保存的路径，若不指定则保存在当前目录下.", nargs='?')
        self.parse.add_argument('-r', '--recursive', help="递归的下载目录，若是下载目录则需要指定该选项", action='store_true')
        self.help_info = self.parse.format_help()
        self.session = session

    @property
    def command_name(self) -> str:
        return 'download'

    @property
    def command_type(self) -> CommandType:
        return CommandType.FILE_COMMAND

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        local_path:str = args.local_path
        source_path:str = args.source_path
        if local_path is None:
            local_path = os.path.basename(source_path.replace(self.session.server_info.sep, os.sep))

        local_path = os.path.abspath(local_path)
        fname = os.path.basename(source_path.replace(self.session.server_info.sep, os.sep))
        if os.path.exists(local_path):
            if os.path.isfile(local_path):
                if input(f"`{local_path}`本地文件存在，是否覆盖?(y/n) ").lower() != 'y':
                    return CommandReturnCode.CANCEL
            elif os.path.isdir(local_path): # 如果指定的本地路径为目录，那么会把下载的文件或目录放在该目录下
                for f in os.listdir(local_path):
                    if f.lower() == fname.lower():
                        if os.path.isdir(f):# 不准有同名目录
                            logger.error(f"本地目录`{local_path}`包含一个同名目录`{f}`!")
                            return CommandReturnCode.FAIL
                        if input(f"`{local_path}`本地目录包含同名文件`{fname}`，是否覆盖?(y/n) ").lower() != 'y':
                            return CommandReturnCode.CANCEL
                        break
        else:
            dirname = os.path.dirname(local_path.rstrip(os.sep))
            if not os.path.exists(dirname):
                logger.error(f"无法递归创建路径`{local_path}`，请手动创建或指定新路径！")
                return CommandReturnCode.FAIL
        logger.info("正在下载...")
        ret = self.download(source_path, local_path, args.recursive)
        if ret == CommandReturnCode.SUCCESS:
            logger.info("所有文件下载完毕!")
        return ret

    def download(self, server_path: str, local_path: str, r: bool)-> CommandReturnCode:
        ret = self.session.evalfile('download', dict(pwd=self.session.server_info.pwd, path=server_path))
        if ret is None:
            logger.error(f"下载`{server_path}`发生错误!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 1:
            with open(local_path, 'wb') as f:
                data = base64.b64decode(ret['msg'].encode())
                f.write(data)
            logger.info(f'下载文件`{server_path}`成功!', True)
            return CommandReturnCode.SUCCESS
        elif ret['code'] == 2:
            logger.error(f"服务器文件`{server_path}`不可读！权限不足！")
        elif ret['code'] == 0:
            logger.error(f"服务器文件`{server_path}`不存在!")
        elif ret['code'] == -2:
            logger.error(f"服务器文件`{server_path}`不是一个已知的文件类型!")
        elif ret['code'] == -1:
            logger.error(f"服务器目录`{server_path}`不可列文件！权限不足！")
        elif ret['code'] == -3:
            if r:# 递归的下载目录
                logger.info(f'正在下载目录`{server_path}`...')
                sep = ret['msg']
                if not os.path.exists(local_path):
                    os.mkdir(local_path)
                ret = self.session.evalfile('listdir', dict(path=server_path, pwd=self.session.server_info.pwd))
                if ret is None:
                    logger.error(f"列举目录`{server_path}`错误！目录下载失败！")
                    return CommandReturnCode.FAIL
                ret = json.loads(ret)
                if ret['code'] == 1:
                    l = ret['list']
                    tmp = CommandReturnCode.SUCCESS
                    for fname in l:
                        fname = base64.b64decode(fname.encode()).decode(self.session.options.get_option('encoding'), 'ignore')
                        if self.download(server_path+sep+fname, os.path.join(local_path, fname), r) != CommandReturnCode.SUCCESS:
                            tmp = CommandReturnCode.PARTIAL_SUCCESS
                    return tmp
                else:
                    logger.error(f"列举目录`{server_path}`失败！目录下载失败！")
            else:
                logger.error(f"服务器文件`{server_path}`是一个目录！你可以指定`-r`选项用于下载目录.")
        
        return CommandReturnCode.FAIL

        