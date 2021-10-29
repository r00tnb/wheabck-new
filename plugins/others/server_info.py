from os import pardir, pwrite
from api import Plugin, colour, Session, Command, CommandType, CommandReturnCode, Cmdline, session, tablor
import time, argparse

def get_plugin_class():
    return ServerInfoPlugin

class ServerInfoPlugin(Plugin, Command):

    name = 'server_info'
    description = '显示远程系统基本信息'
    command_name = 'server_info'
    command_type = CommandType.MISC_COMMAND

    def __init__(self):
        self.help_info = self.description

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)


    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        table = [['名称', '值'],
            ['网站 ', self.session.server_info.website],
            ['webshell文件地址', self.session.server_info.webshell_addr],
            ['网站根目录', self.session.server_info.www_root],
            ['系统类型', self.session.server_info.os_type.name],
            ['工作目录', self.session.server_info.pwd],
            ['用户名', self.session.server_info.user],
            ['用户组名', self.session.server_info.group],
            ['主机域名', self.session.server_info.domain],
            ['IP地址', self.session.server_info.ip_addr],
            ['临时目录', self.session.server_info.tmpdir],
            ['目录分割符', self.session.server_info.sep],
            ['操作系统位数', self.session.server_info.os_bit],
        ]
        print(tablor(table, border=False))
        return CommandReturnCode.SUCCESS