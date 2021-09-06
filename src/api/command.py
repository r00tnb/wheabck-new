import abc
from typing import List
from .maintype.info import CommandReturnCode, CommandType
from .ui.cmdline import Cmdline

class Command(metaclass=abc.ABCMeta):
    '''命令类，所有可运行的命令需要继承该类
    '''
    description = '' # 命令的简短描述
    help_info = '' # 命令的帮助信息
    command_name = '' # 命令名称
    command_type = CommandType.MISC_COMMAND # 命令类型
    
    @abc.abstractmethod
    def run(self, cmdline:Cmdline)->CommandReturnCode:
        """运行命令行中传来的命令

        Args:
            cmdline (Cmdline): 命令行

        Returns:
            CommandReturnCode: 返回命令的退出代码
        """