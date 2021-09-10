import abc

from .ui.cmdline import Cmdline
from .command import Command

from .executor import CommandExecutor
from .maintype.payload import Payload
from .maintype.info import AdditionalData, CommandReturnCode, CommandType, SessionOptions, SessionType, ServerInfo
from typing import Any,Dict, List, Tuple, Union, Callable


class Session(metaclass=abc.ABCMeta):
    '''session用于描述当前webshell的信息，并提供工具方法
    '''

    ## 属性
    @abc.abstractproperty
    def is_loaded(self)-> bool:
        """判断当前session是否已经加载完毕

        Returns:
            bool: 当所有插件均已加载完毕时返回True，否则False
        """

    
    @abc.abstractproperty
    def options(self)->SessionOptions:
        """获得session选项实例

        Returns:
            SessionOptions: session选项实例
        """


    @abc.abstractproperty
    def session_id(self)->str:
        '''获取一个唯一标识session的字符串
        '''

    @abc.abstractproperty
    def session_type(self)->SessionType:
        '''获取当前session类型

        :returns: SessionType
        '''

    @abc.abstractproperty
    def server_info(self)->ServerInfo:
        '''获取远程服务器的基本信息

        :returns: ServerInfo
        '''

    @abc.abstractproperty
    def additional_data(self)->AdditionalData:
        """返回当前session的额外数据字典，一般用于session扩展存储的数据

        Returns:
            AdditionalData: 额外数据字典
        """

    @abc.abstractproperty
    def plugins_list(self):
        """返回当前session加载的插件实例列表

        Returns:
            Tuple[Plugin, ...]: 插件实例列表
        """

    ## 方法

    @abc.abstractmethod
    def save_json(self, name: str, value:Union[list,dict, None])-> bool:
        '''保存一个json对象到当前session,在同一个连接下，若已存在一个相同名称的json数据则会覆盖，若value为None则删除该json数据

        :param name: 为保存的对象起的名字，名字存在则会覆盖
        :param value: 一个可被序列化为json字符串的对象,若为None则删除该条json数据
        :returns: bool,保存成功返回True，否则False
        '''

    @abc.abstractmethod
    def load_json(self, name:str)->Union[list, dict, None]:
        '''从当前session加载一个已保存的json对象

        :param name: json对象的名字
        :returns: 若存在则返回一个保存前的json对象，失败返回None
        '''

    @abc.abstractmethod
    def eval(self, payload:Payload, timeout:float=-1)->Union[bytes, None]:
        """执行payload代码并获取执行结果,不会验证payload是否是当前session支持的

        Args:
            payload (Payload): payload实例
            timeout (float, optional): 本次执行payload的超时时间(单位秒)，设置为0则无限等待，设置为小于0则使用默认超时时间. Defaults to -1.

        Returns:
            Union[bytes, None]: 执行结果，失败返回None
        """
    
    @abc.abstractmethod
    def evalfile(self, payload_path:str, vars:Dict[str, Any]={}, timeout:float=-1)->Union[bytes, None]:
        """执行指定路径下的payload文件并获取执行结果。
        若传入的文件路径不带后缀，该方法将根据当前session类型读取同目录下相应的payload文件。
        该方法会根据session类型自动构造对应的payload实例并调用eval方法执行（若文件后缀不是session支持的则会构造失败）。

        Args:
            payload_path (str): payload文件路径，该路径可以是绝对路径，也可以是相对路径，当为相对路径时，它相对的是调用该方法的文件的路径。
            vars (Dict[str, Any], optional): 向该payload传递的全局变量字典. Defaults to {}.
            timeout (float, optional): 本次执行payload的超时时间(单位秒)，设置为0则无限等待，设置为小于0则使用默认超时时间. Defaults to -1.

        Returns:
            Union[bytes, None]: 执行结果，失败返回None
        """

    @abc.abstractmethod
    def exec(self, cmd:bytes, timeout:float=-1)->Union[bytes, None]:
        """执行系统命令，并获取命令输出的结果

        Args:
            cmd (bytes): 命令字节流
            timeout (float, optional): 本次执行命令的超时时间(单位秒)，设置为0则无限等待，设置为小于0则使用默认超时时间. Defaults to -1.

        Returns:
            Union[bytes, None]: 命令的输出结果，只获取标准输出流内容，对于错误输出需要在命令中使用重定向来获取。若执行错误（系统命令错误之外的错误）则返回None
        """

    @abc.abstractmethod
    def set_default_exec(self, plugin_id:str)->bool:
        """设置当前默认的命令执行器，将会从当前session已加载的插件中寻找

        Args:
            plugin_id (str): 命令执行器的插件ID

        Returns:
            bool: 成功返回True，否则False
        """

    @abc.abstractmethod
    def register_complete_func(self, func:Callable[[str], List[str]]):
        '''注册一个命令补全函数（在控制台下有效）

        :param func: 一个命令补全函数,其中第一个参数为此次请求补全的命令行字符串， 返回值为补全后的字符串候选列表
        '''

    @abc.abstractmethod
    def register_command(self, command:Command):
        """注册一个命令

        通过该函数可直接注册一个命令。若插件通过继承同时继承了Command类，session将自动注册该命令，无需使用该函数注册

        Args:
            command (Command): 一个继承自Command的子类
        """

    @abc.abstractmethod
    def call_command(self, cmdline:Union[Cmdline, List[str], str])->Union[CommandReturnCode, None]:
        """执行一个当前session中的命令

        Args:
            cmdline (Union[Cmdline, List[str], str]): 将要执行的命令行，可以是Cmdline实例，字符串列表或字符串

        Returns:
            Union[CommandReturnCode, None]: 返回命令行的返回代码,若命令行解析错误则返回None（如命令不存在等）
        """