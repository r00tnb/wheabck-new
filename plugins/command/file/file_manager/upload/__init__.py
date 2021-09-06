from api import logger, Cmdline, Command, Session, CommandReturnCode, CommandType
import argparse
import base64
import tempfile
import os
import json
import re
import math

class UploadCommand(Command):
    description = "上传文件到远程服务器"
    command_name = 'upload'
    command_type = CommandType.FILE_COMMAND

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('local', help="本地文件路径.")
        self.parse.add_argument('remote', help="远程文件路径.", nargs='?')
        self.parse.add_argument('-f', '--force', help="若远程文件存在，则不加询问的覆盖")
        self.parse.add_argument('-s', '--uploadsize', help="每次上传的数据包大小。能够使用单位b（字节）、k（千字节）、m（兆字节）默认b.例如1024, 1024b, 1024k等。若设置为0（默认），则文件内容将在一次请求中上传", 
            type=self._getsize, default="0")
        self.help_info = self.parse.format_help()
        self.session = session

        self.session.register_complete_func(self.docomplete)


    def _getsize(self, size: str)-> int:
        '''用于转换传入的--uploadsize参数
        '''
        size = size.strip().rstrip('bB').lower()
        try:
            util = size[-1]
            if util not in 'km':
                return int(size)

            size = float(size[:-1])
            if util == 'k':
                size *= 1024
            elif util == 'm':
                size *= 1024*1024
            return int(size)
        except Exception as e:
            logger.error(f"上传数据包大小参数`{size}`格式错误!")
            raise e

    def run(self, args:Cmdline)-> int:
        args = self.parse.parse_args(args.options)
        local = os.path.abspath(args.local)
        if not os.path.isfile(local):
            logger.error(f"本地文件`{local}`不存在或不是一个文件!")
            return CommandReturnCode.FAIL
        
        data = b''
        with open(local, 'rb') as f:
            data = f.read()
        remote = args.remote
        if remote is None:
            remote = os.path.basename(local)
        if remote.endswith('/') or remote.endswith('\\'):
            remote += os.path.basename(local)
        logger.info(f'上传文件`{local}`...')
        return self._upload(remote, data, False if args.force is None else args.force, args.uploadsize)

    def _upload(self, remote:str, data:bytes, force: bool, uploadsize: int)->int:
        '''将数据写入到远程文件
        '''
        sign = 1 if force else 0
        total = math.ceil(len(data)/uploadsize) if uploadsize > 0 else 1
        progress = 0
        while data:
            block = data[:uploadsize] if uploadsize > 0 else data
            data = data[uploadsize:] if uploadsize > 0 else b''
            ret = self.session.evalfile('upload', dict(pwd=self.session.server_info.pwd, path=remote, data=block, sign=sign))
            sign = 2
            while ret is None:
                if total>1:# 如果分片上传时失败，则重传一次该分片
                    ret = self.session.evalfile('upload', dict(pwd=self.session.server_info.pwd, path=remote, data=block, sign=sign))
                    if ret is not None:
                        break
                logger.error("文件上传错误!")
                return CommandReturnCode.FAIL
            if ret == b'0':
                logger.warning(f"远程文件`{remote}`已存在！")
                if input("你想覆盖这个文件吗?(y/n) ").lower() == 'y':
                    return self._upload(remote, block+data, True, uploadsize)
                return CommandReturnCode.CANCEL
            elif ret == b'-1':
                logger.error(f"远程文件`{remote}`打开失败，检查远程文件路径是否正确或者是否有足够的权限!")
                return CommandReturnCode.FAIL
            elif ret == b'1':
                if total > 1:
                    progress += 1
                    per = str(int(progress/total*100))+'%'
                    per = per.rjust(4, ' ')
                    print(f"文件上传进度 {per} ({progress}/{total}).", end='\r' if progress<total else ' 完毕！\n', flush=True)
                continue
            else:
                print(f"sdfsd: {ret}")
                logger.error("发生了未知错误!")
                return CommandReturnCode.FAIL
        logger.info(f"上传文件`{remote}`成功!")
        return CommandReturnCode.SUCCESS

    def docomplete(self, text: str):# 本地文件路径补全
        result = []
        match = re.compile(r'''^(upload +)(["'`]?)([\w\-/\\.]*)$''', re.M).search(text)
        if match:
            dirname, name = os.path.split(match.group(3))
            dirpath = os.path.abspath(dirname)
            if not os.path.isdir(dirpath):
                return result
            for f in os.listdir(dirpath):
                if f.startswith(name):
                    if os.path.isdir(os.path.join(dirpath, f)):
                        result.append(match.group(1)+match.group(2)+os.path.join(dirname, f)+'/')
                    else:
                        result.append(match.group(1)+match.group(2)+os.path.join(dirname, f)+match.group(2)+' ')

        return result