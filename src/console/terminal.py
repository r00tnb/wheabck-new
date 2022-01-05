import importlib
import os

from .sessionmanager import ManagerSession
from src.core.connectionmanager import Connection
from src.api.command import Command
from typing import Dict, List
import src.config as config
from src.api import logger, Cmdline, colour
from src.api.maintype.info import CommandReturnCode
from src.core.sessionadapter import SessionAdapter
from src.core.pluginmanager import plugin_manager
import builtins, sys

__all__ = ['terminal']

def _my_input(prompt:str='')->str:
    '''用于替换全局的input函数

    :param prompt: 提示字符串
    :returns: 返回获取的输入
    '''
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().rstrip('\n')


_raw_input = builtins.input # 保存原始的input函数
builtins.input = _my_input


class Terminal:
    '''实现命令行终端交互功能
    '''

    def __init__(self):
        
        self._readline = None # 指示是否包含readline库
        
        try:
            self._readline = importlib.import_module('readline')
            self._readline.set_completer(self.complete)
            self._readline.set_completer_delims('')
            self._readline.parse_and_bind('tab: complete')
            self._readline.clear_history()
            if os.path.exists(config.history_path):
                self._readline.read_history_file(config.history_path)
            if hasattr(self._readline, 'set_auto_history'):
                self._readline.set_auto_history(False)
        except ModuleNotFoundError:
            logger.warning("No module `readline`! You can type `pip install readline` to install it in Unix platform, or `pip install pyreadline` in windows platform.")
            logger.info("You can ignore this warning, but command will not be auto-completed and command history is not available.")
            self._readline = None

        self.manager_session:ManagerSession = None  # 用于管理其他session

        # 初始化
        plugins_dir_list = [os.path.join(os.path.dirname(__file__), 'core_plugins')]
        for d in os.listdir(config.plugins_path):
            plugins_dir_list.append(os.path.join(config.plugins_path, d))
        win = plugin_manager.load_all_plugins(plugins_dir_list)
        logger.info(f"Loaded {win} plugins!")

        self.manager_session = ManagerSession()

    @property
    def session(self)->SessionAdapter:
        '''返回当前正在使用的session对象
        '''
        return self.manager_session.current_session
    
    def interrupt_handler(self, args: Cmdline)-> CommandReturnCode:
        '''处理Ctrl+C中断异常

        :param args: 引起中断时的命令行
        :returns: 返回命令退出代码
        '''
        print('')
        try:
            return self.manager_session.call_command(['exit'])
        except KeyboardInterrupt:
            print('')
            return CommandReturnCode.EXIT
        #return CommandReturnCode.FAIL
    
    def exception_handler(self, args: Cmdline, e: BaseException) -> CommandReturnCode:
        '''处理异常

        :param args: 引起异常时的命令行
        :param e: 异常对象
        :returns: 返回命令退出代码
        '''
        if not isinstance(e, SystemExit):
            raise e
        return CommandReturnCode.FAIL

    def parsecmd(self, line: str)-> Cmdline:
        '''解析命令行字符串为命令行对象

        :param line: 命令行字符串
        :returns: 返回命令行对象
        '''
        return Cmdline(line)
        
    def precmd(self, args: Cmdline)-> Cmdline:
        '''命令执行前调用

        :param args: 命令行
        :returns: 返回命令行
        '''
        if self._readline is not None and args.cmd is not None:
            self._readline.add_history(args.cmdline)
        return args

    def cmdhandler(self, args: Cmdline)-> CommandReturnCode:
        '''处理命令执行

        :param args: 命令行
        :returns: 命令退出代码
        '''
        if args.cmd is None:
            return CommandReturnCode.FAIL
        cmd = args.cmd
        command = self.session.command_map.get(cmd, None)
        if command is not None:
            ret = command.run(args)
            logger.debug(f'A command line `{args.cmdline}` is executed, returns `{ret}`')
            return ret

        logger.error(f'No command named `{cmd}`.')
        return CommandReturnCode.FAIL

    def postcmd(self, stop: int, args: Cmdline)-> CommandReturnCode:
        '''命令执行结束后调用'''
        return stop

    def preloop(self):
        '''命令循环之前执行'''
        pass

    def postloop(self):
        '''退出命令循环后执行
        '''
        self._readline.set_history_length(1000)
        self._readline.write_history_file(config.history_path)
        self.manager_session.on_destroy_before()

    @property
    def prompt(self)->str:
        '''返回的字符串作为提示符
        '''
        return self.manager_session.prompt

    def complete(self, text: str, state: int):
        matchs = []
        for autocomplete in self.session.autocomplete_list:
            matchs = autocomplete(text)
            if matchs:
                break
        
        if state < len(matchs):
            return matchs[state]

        return None

    def cmdloop(self):
        '''命令循环
        '''
        line  = ''
        args = []
        stop = CommandReturnCode.SUCCESS
        logger.debug(f"Start the command loop on class `{__class__.__name__}`")
        self.preloop()
        while stop != CommandReturnCode.EXIT:
            try:
                line = _raw_input(self.prompt)
                if line == '':
                    continue
                try:
                    args = self.parsecmd(line)
                except ValueError as e:
                    logger.debug('Failed to parse the command line')
                    logger.error(str(e))
                    continue

                args = self.precmd(args)

                stop = self.cmdhandler(args)
                stop = self.postcmd(stop, args)
            except (KeyboardInterrupt, EOFError):
                stop = self.interrupt_handler(args)
            except BaseException as e:
                stop = self.exception_handler(args, e)
                
        self.postloop()
        logger.debug(f"End the command loop on class `{__class__.__name__}`")

terminal = Terminal()