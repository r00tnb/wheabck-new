import os
import re
from src.api.ui.cmdline import Cmdline
from src.api.ui.logger import logger
from src.api.ui.color import colour
from src.api.command import Command
from src.api.maintype.payload import PHPPayload
from src.api.wrapper import Wrapper
from src.api.executor import CodeExecutor, CommandExecutor
from src.api.maintype.payload import Payload
from src.api.plugin import Plugin
from src.api.session import Session
from src.api.maintype.info import AdditionalData, CommandReturnCode, CommandType, ServerInfo, SessionOptions, SessionType
import src.api.maintype.utils as utils
from .pluginmanager import plugin_manager
from .connectionmanager import Connection, connection_manager
from typing import Any, Callable, Dict, List, Tuple, Type, Union

class SessionInitError(Exception):
    '''session初始化失败的错误
    '''


class SessionAdapter(Session):
    '''实现Session类,session必须从Connection实例建立
    '''

    def __init__(self, config: Connection, strict:bool=True):
        '''
        :param config: session配置对象
        :param strict: 当为真时，session必须有一个可用的代码执行器
        '''
        self.config = config
        # 已加载的插件实例字典,不包括代码执行器和包装器
        self.__plugin_instance_map: Dict[str, Plugin] = {}
        self.__loaded = False  # 是否加载完毕
        self.__id = utils.random_str()  # session id
        self.__complete_func_list:List[Callable[[str], List[str]]] = [] # 命令补全函数列表
        self.__command_map:Dict[str, Command] = {} # 当前session中注册的命令
        self.__additional_data:AdditionalData = AdditionalData() # 当前session使用的额外数据字典

        self.register_complete_func(self.command_complete) # 注册默认的命令补全


        # 初始化代码执行器和payload包装器，它们不会加载到__plugin_instance_map中
        self.__code_executor: CodeExecutor = plugin_manager.get_code_executor(
            self.config.options.get_option('code_executor_id'))
        if self.__code_executor is not None:
            if self.config.session_type not in self.__code_executor.supported_session_types or not self.__code_executor.on_loading(self):
                raise SessionInitError(
                    f'Code executor with ID {self.config.options.get_option("code_executor_id")} is not support the session!')
        elif strict:
            raise SessionInitError(
                f'Code executor with ID {self.config.options.get_option("code_executor_id")} is not found!')

        self.__payload_wrapper: Wrapper = plugin_manager.get_wrapper(self.config.options.get_option('wrapper_id'))
        if self.__payload_wrapper is None or self.session_type not in self.__payload_wrapper.supported_session_types or \
                not self.__payload_wrapper.on_loading(self):
            self.__payload_wrapper = plugin_manager.get_default_wrapper()
            self.options.set_option('wrapper_id', self.__payload_wrapper.plugin_id)

        # 命令执行器一般在__plugin_instance_map中(此时会在加载插件时初始化)，也可能是代码执行器或包装器
        self.__command_executor: CommandExecutor = None
        if self.config.options.get_option('command_executor_id') == self.config.options.get_option("code_executor_id") and \
                isinstance(self.__code_executor, CommandExecutor):
            self.__command_executor = self.__code_executor
        if self.config.options.get_option('wrapper_id') == self.config.options.get_option('command_executor_id') and \
                isinstance(self.__payload_wrapper, CommandExecutor):
            self.__command_executor = self.__payload_wrapper

    def on_destroy_before(self):
        '''session销毁后执行
        '''
        # 执行相应回调
        for plugin in self.__plugin_instance_map.values():
            plugin.on_destroy()
        if self.__payload_wrapper:
            self.__payload_wrapper.on_destroy()
        if self.__code_executor:
            self.__code_executor.on_destroy()

    def __str__(self) -> str:
        return f"{self.session_type.name}/{self.__code_executor.name if isinstance(self.__code_executor, Plugin) else 'session_manager'}"


    @property
    def autocomplete_list(self)->List[Callable[[str], List[str]]]:
        '''返回命令自动补全的函数列表
        '''
        return self.__complete_func_list.copy()

    @property
    def session_type(self) -> SessionType:
        return self.config.session_type

    @property
    def server_info(self) -> ServerInfo:
        return self.config.server_info

    @property
    def additional_data(self) -> Dict[str, Any]:
        return self.__additional_data

    @property
    def code_executor(self)->Union[CodeExecutor, None]:
        """返回当前session使用的代码执行器实例

        Returns:
            CodeExecutor: 代码执行器实例,若session不需要代码执行器则返回None
        """
        return self.__code_executor

    @property
    def is_loaded(self) -> bool:
        return self.__loaded

    @property
    def options(self) -> SessionOptions:
        return self.config.options

    @property
    def plugins_list(self) -> Tuple[Plugin, ...]:
        '''注意：返回的插件列表是包含代码执行器和payload包装器的插件列表
        '''
        return tuple(self.__plugin_instance_map.values())+(self.__code_executor, self.__payload_wrapper)

    @property
    def command_map(self)->Dict[str, Command]:
        """返回session中注册的命令

        Returns:
            Dict[str, Command]: session中注册的命令字典
        """
        return self.__command_map.copy()

    @property
    def session_id(self) -> str:
        return self.__id

    def init_session(self)->bool:
        """初始化session，用于进行正常的session交互

        步骤：
            1.加载插件
            2.尝试获取服务器基本信息，成功则初始化成功否则失败

        Returns:
            bool: 成功返回True，否则False
        """
        logger.info(f"Connecting to target `{self.options.get_option('target')}`...")
        try:
            self.config.server_info = self.__code_executor.get_server_info()
        except BaseException as e:
            logger.error(f"Failed to get basic server information, by {e}")
            return False
        if self.config.server_info is None:
            logger.error(f"Failed to get basic server information")
            return False

        self.additional_data.prompt = lambda :colour.colorize(self.server_info.server_name, 'bold', 'purple')+\
            ':'+colour.colorize(self.server_info.pwd, 'bold', 'blue')+colour.colorize('\n> ', 'bold')
        logger.info(f"`{self.load_all_plugins()}` plugins loaded")
        logger.info(f"Session `{self.session_id}` initialization completed")
        return True


    def load_plugin(self, plugin_class:Type[Plugin])->bool:
        '''向当前session加载一个除代码执行器和payload包装器之外的插件(此种方式加载的插件不会触发on_loaded回调,需要在适当的时机自己调用)

        :param plugin_class: 一个除代码执行器和payload包装器之外的插件，这个插件类应该来自插件管理类中
        :returns: 成功返回True，否则False
        '''
        if self.session_type not in plugin_class.supported_session_types:
            return False
        if issubclass(plugin_class, (CodeExecutor, Wrapper)):
            return False
        plugin = plugin_class()
        if plugin.on_loading(self):
            if isinstance(plugin, Command):# 如果是命令插件则注册命令
                self.register_command(plugin)

            self.__plugin_instance_map[utils.random_str()] = plugin
            if self.__command_executor is None and self.config.options.get_option('command_executor_id') == plugin.plugin_id and \
                    isinstance(plugin, CommandExecutor):  # 初始化命令执行器
                self.__command_executor = plugin
            return True
        return False

    def on_loaded(self):
        """执行所有插件的on_loaded回调
        """
        if self.__code_executor:
            self.__code_executor.on_loaded()
        self.__payload_wrapper.on_loaded()
        for plugin in self.__plugin_instance_map.values():
            plugin.on_loaded()

        self.__loaded = True

    def load_all_plugins(self) -> int:
        '''从插件管理器中加载插件实例，返回加载成功的插件数量,在加载完毕后会触发所有插件的on_loaded回调

        :returns: int, 加载成功的插件数量
        '''
        ret = 0
        for ID, plugin_class in plugin_manager.plugins_map.items():
            if self.load_plugin(plugin_class):
                ret += 1

        self.on_loaded()
        return ret

    def load_json(self, name: str) -> Union[list, dict, None]:
        return connection_manager.get_json_data(self.config.conn_id, name)

    def save_json(self, name: str, value: Union[list, dict, None]) -> bool:
        if value is None:
            connection_manager.del_json_data(self.config.conn_id, name)
        elif connection_manager.get_json_data(self.config.conn_id, name) is None:
            connection_manager.add_json_data(self.config.conn_id, name, value)
        else:
            connection_manager.update_json_data(self.config.conn_id, name, value)

    def eval(self, payload: Payload, timeout: float = None) -> Union[bytes, None]:
        code = payload.code
        if self.__payload_wrapper:
            code = self.__payload_wrapper.wrap(code)
        if timeout is None or timeout < 0:
            timeout = self.config.options.get_option('timeout')
        return self.__code_executor.eval(code, timeout)

    def evalfile(self, payload_path: str, vars: Dict[str, Any] = {}, timeout: float = None) -> Union[bytes, None]:
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(utils.call_path(2)))  # 切换到调用该函数处的文件所在目录
        if not payload_path.lower().endswith(self.session_type.suffix):
            payload_path += self.session_type.suffix
        code = utils.file_get_content(payload_path)
        os.chdir(old_dir)
        if code is None:
            return None
        p = Payload.create_payload(code, vars, self.session_type)

        return self.eval(p, timeout)

    def exec(self, cmd: bytes) -> Union[bytes, None]:
        return self.__command_executor.exec(cmd)

    def exec(self, cmd: bytes, timeout: float=-1) -> Union[bytes, None]:
        return self.__command_executor.exec(cmd)

    def set_default_exec(self, executor: CommandExecutor) -> bool:
        if not issubclass(executor, CommandExecutor):
            return False
        self.__command_executor = executor
        self.config.options.set_option('command_executor_id', plugin_manager.get_plugin_id(executor))
        return True

    def register_complete_func(self, func: Callable[[str], List[str]]):
        self.__complete_func_list.append(func)

    def register_command(self, command: Command):
        if command.command_name in self.__command_map:
            return
        self.__command_map[command.command_name] = command

    def call_command(self, cmdline: Cmdline) -> Union[CommandReturnCode, None]:
        for c in self.command_map.values():
            if c.command_name == cmdline.cmd:
                return c.run(cmdline)
        return None

    def command_complete(self, text:str)->List[str]:
        '''自动补全已存在的命令
        '''
        matchs = []
        for p in self.__command_map.values():
            if p.command_name.lower().startswith(text.lower()):
                matchs.append(p.command_name+' ')
        return matchs