from api import logger, Command, Cmdline, CommandReturnCode, CommandType, Session, colour, tablor
import argparse
import os
import re
import json
import time
import base64

class LsCommand(Command):
    description = "列出指定路径下的文件信息"

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog="ls", description=self.description)
        self.parse.add_argument('path', help="远程文件或目录路径，不指定则列当前目录.", nargs='?')
        self.help_info = self.parse.format_help()
        self.session = session

    @property
    def command_name(self) -> str:
        return 'ls'

    @property
    def command_type(self) -> CommandType:
        return CommandType.FILE_COMMAND

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        path = args.path
        if path is None:
            path = self.session.server_info.pwd
        ret = self.session.evalfile('ls', dict(pwd=self.session.server_info.pwd, path=path))
        if ret is None:
            logger.error("文件列出错误!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 1:
            table = [['权限位', '属主', '属组', '大小', '上次修改时间', '文件/目录名称']]
            for item in ret['msg']:
                l = []
                l.append(item[0])
                l.append(item[1] if item[1] != '(未知)' else colour.colorize(item[1], 'note'))
                l.append(item[2] if item[2] != '(未知)' else colour.colorize(item[2], 'note'))
                l.append(self._format_size(item[3]))
                l.append(self._format_time(item[4]))
                tmp = base64.b64decode(item[5].encode()).decode(self.session.options.get_option('encoding'), 'ignore')
                l.append(self._format_filename(tmp, item[0]))
                table.append(l)
            print(tablor(table, border=False, autocolor=False, aligning='right-4', indent=' '))
            return CommandReturnCode.SUCCESS
        elif ret['code'] == -1:
            logger.error(f"路径`{path}`不存在或者你无权访问!")
        elif ret['code'] == -2:
            logger.error(f"路径`{path}`无法列文件！")

        return CommandReturnCode.FAIL

    def _format_size(self, size: int)-> str:
        unit = 'B'
        if size>9999:
            size /= 1024
            unit = 'KB'
        if size>9999:
            size /= 1024
            unit = 'MB'
        if size>9999:
            size /= 1024
            unit = 'GB'
        if size>9999:
            size /= 1024
            unit = 'TB'
        if size>9999:
            size /= 1024
            unit = 'PB'
        size = round(size, 2)
        if size-int(size) == 0:
            size = int(size)
        return str(size)+unit

    def _format_time(self, timestamp: int)-> str:
        time_local = time.localtime(timestamp)
        return time.strftime("%Y-%m-%d %H:%M:%S", time_local)

    def _format_filename(self, filename: str, perm: str)-> str:
        ret = filename
        is_all = True if '-' not in perm[1:] else False # 权限位是否是777
        color = {'fore':None, 'mode':'bold'}
        if perm[0] == 'd':
            color['fore'] = 'blue'
            if is_all:
                color['mode'] = ['bold', 'invert']
        elif perm[0] == 's':
            color['fore'] = 'purple'
        elif perm[0] == 'l':
            return colour(filename, [
                {
                    'regexp':r'^(.*?) ->',
                    'color':['bold', 'cyan', '']
                }
            ])
        elif perm[0] == 'p':
            color['fore'] = 'red'
        elif perm[0] == '-' and is_all:
            color['fore'] = 'green'
        if color['fore'] is not None:
            ret = colour.colorize(ret, **color)
        return ret