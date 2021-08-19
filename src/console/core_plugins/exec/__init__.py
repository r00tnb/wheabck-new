import argparse
from .cmd import CSharpCmd, PHPCmd, CmdOnServer
from .shell.by_namedpipe import NamedpipeUnixShell
from .shell.base import BaseShell, NormalShell
from typing import Union
from api import Plugin, Command, Cmdline, CommandReturnCode, Session, CommandType, colour, CommandExecutor, logger, OSType, SessionType

def get_plugin_class():
    return ExecPlugin

class ExecPlugin(Plugin, Command, CommandExecutor):
    name = 'exec'
    description = "在远程服务器上执行系统命令"
    
    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.parse.add_argument('command', nargs='?', help="要执行的命令行.")
        self.parse.add_argument("-e", "--raw-executor", help="使用自带的命令执行器执行命令，不指定该选项则使用session配置中的命令执行器", 
            action="store_true")
        interact_group = self.parse.add_argument_group("交互式shell选项")
        interact_group.add_argument('-i', "--interactive", help="指定交互式shell命令并运行，如 `sh -i 2>&1`（不指定则这是默认的）", nargs='?', const=True)
        interact_group.add_argument("-t", "--type", help="指定以何种方式运行交互式命令，base（仅提供模拟交互的命令执行）、\
            normal（提供基本真实的交互，可进行pty获取操作，基于文件通信）以及\
            namedpipe（类似normal，基于命名管道通信，只适用于Linux系统）.", choices=["normal", "base", "namedpipe"])

        self.methods = []
        self.executor:CmdOnServer = None


    def on_loading(self, session: Session) -> bool:
        if session.session_type == SessionType.PHP:
            self.executor = PHPCmd(session, 'auto')
        elif session.session_type == SessionType.ASP_NET_CS:
            self.executor = CSharpCmd(session, 'shell')

        php_methods = ['exec','passthru', 'popen', 'proc_open', 'shell_exec', 'wscript', 'auto'] 
        asp_net_methods = ['shell', 'process']
        self.methods = php_methods # 默认是PHP的方法列表
        if session.session_type == SessionType.ASP_NET_CS:
            self.methods = asp_net_methods
        setting_group = self.parse.add_argument_group("命令执行方法选项")
        setting_group.add_argument("-s", "--show-methods", help="显示当前命令执行使用的函数", action="store_true")
        setting_group.add_argument("-m", "--executor-method", 
            help=f"设置使用哪个函数来执行命令.PHP命令执行函数: {', '.join(php_methods)}(自动遍历可使用的函数).\
            ASP.NET命令执行函数: {', '.join(asp_net_methods)}", 
            choices=self.methods)
        self.help_info = self.parse.format_help()
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.interactive:
            return self.interactive(args.interactive, args.type)
        elif args.show_methods:
            self.show_methods()
        elif args.executor_method:
            self.executor.method = args.executor_method
            self.show_methods()
        elif args.command is not None:
            return self.exec_command_on_server(args.command, args.raw_executor)
        else:
            print(self.help_info)

        return CommandReturnCode.SUCCESS

    def show_methods(self):
        '''显示当前命令执行方法信息
        '''
        print("当前使用的命令执行方法: ", self.executor.method)
        ok = self.methods.copy()
        for i in range(len(ok)):
            if ok[i] == self.executor.method:
                ok[i] = colour.colorize(ok[i], ['bold', 'invert'])
        print("所有可用的命令执行方法: ", '|'.join(ok))

    def exec(self, cmd: bytes) -> Union[bytes, None]:
        if self.executor:
            return self.executor.exec(cmd)
        return None

    def exec_command_on_server(self, cmd:str, use_raw:bool)->CommandReturnCode:
        """在服务器上执行系统命令

        Args:
            cmd (str): 命令字符串
            use_raw (bool): 是否使用插件自带的命令执行器，否则使用session配置的命令执行器

        Returns:
            CommandReturnCode: 命令返回码
        """
        result:bytes = None
        if use_raw:
            result = self.exec(cmd.encode())
        else:
            result = self.session.exec(cmd.encode())
        if result is not None:
            print(result.decode(self.session.options.get_option('encoding')))
        else:
            logger.error(f"Command `{cmd}` exec failed!")
            return CommandReturnCode.FAIL

        return CommandReturnCode.SUCCESS


    def interactive(self, shell: str, type: str)->CommandReturnCode:
        """进入交互式命令执行模式

        Args:
            shell (str): 交互式命令行
            type (str): 执行该交互式的方法

        Returns:
            CommandReturnCode: 命令返回码
        """
        if shell is True:
            if self.session.server_info.os_type == OSType.WINDOWS:
                shell = "cmd 2>&1"
            else:
                shell = "sh -i 2>&1"
        interact_shell = BaseShell(self.session)
        if type is None:
            type = "base"
        if type == "normal":
            interact_shell = NormalShell(self.session, shell)
        elif type == "namedpipe":
            if self.session.server_info.os_type == OSType.WINDOWS:
                logger.error("Windows系统未实现命名管道的方式!你可以使用`normal`类型来达成几乎相同效果")
                return CommandReturnCode.FAIL
            else:
                interact_shell = NamedpipeUnixShell(self.session, shell)

        interact_shell.cmdloop()
        return CommandReturnCode.SUCCESS

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.SYSTEM_COMMAND