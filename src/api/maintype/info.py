import enum
import copy
import logging
from re import T
from typing import Any, Callable, Dict, List, Tuple, Union

@enum.unique
class CommandReturnCode(enum.Enum):
    '''定义命令执行后的返回值
    '''
    EXIT = enum.auto() # 返回该代码会退出整个程序
    SUCCESS = enum.auto() # 命令执行成功
    FAIL = enum.auto() # 命令因错误而执行失败
    PARTIAL_SUCCESS = enum.auto() # 命令处理多个请求但只有部分成功
    CANCEL = enum.auto() # 命令询问是否执行，但用户选择了取消

    def __eq__(self, o: object) -> bool:
        return isinstance(o, CommandReturnCode) and o.value == self.value

@enum.unique
class CommandType(enum.Enum):
    '''命令类型，预定义命令类型用于给命令分类
    '''
    CORE_COMMAND = enum.auto() # 核心命令，一般为自带的命令
    SYSTEM_COMMAND = enum.auto() # 用于在目标系统执行基础操作的命令，如命令执行、代码执行等
    FILE_COMMAND = enum.auto() # 用于文件操作的命令
    MISC_COMMAND = enum.auto() # 杂项命令
    POST_COMMAND = enum.auto() # 后渗透命令
    GATHER_COMMAND = enum.auto() # 信息收集相关命令

    # def __eq__(self, o: object) -> bool:
    #     return o.value == self.value

@enum.unique
class OSType(enum.Enum):
    '''定义服务器操作系统类型
    '''
    UNIX = enum.auto() # Unix类型
    WINDOWS = enum.auto() # Windows类型
    OSX = enum.auto() # mac osx类型
    OTHER = enum.auto() # 其他类型

    def __eq__(self, o: object) -> bool:
        return o.value == self.value

@enum.unique
class SessionType(enum.Enum):
    '''session的类型枚举，枚举值指定对应webshell的类型，一般它应该为对应脚本后缀名的小写
    '''
    PHP = 'php'
    ASP_NET_CS = 'cs'
    JSP = 'jsp'

    @property
    def suffix(self)->str:
        '''返回session类型对应的后缀名

        :returns: str
        '''
        return '.'+str(self.value)

    def __eq__(self, o: object) -> bool:
        return o.value == self.value


class ServerInfo:
    '''用于描述远程服务器的基本信息
    '''

    def __init__(self):
        self.os_type:OSType = OSType.OTHER
        self.pwd:str = None # 当前工作目录
        self.user:str = None # 当前用户名
        self.group:str = None # 当前用户组名
        self.host:str = None # 服务器主机名
        self.domain:str = None # 当前用户所在域
        self.ip_addr:str = None # 服务器IP地址
        self.tmpdir:str = None # 服务器临时目录
        self.sep:str = '/' # 服务器目录分割符
        self.os_bit:int = 32 # 服务器操作系统位数
        self.webshell_addr = None # webshell脚本文件地址

    @property
    def server_name(self)->str:
        """返回服务器名称

        Returns:
            str: 服务器名称
        """
        return f"{self.domain}\{self.user}@{self.host}"

    @classmethod
    def from_dict(cls, info_dict:Dict[str, Any]):
        """从字典中生成ServerInfo实例,只有键与属性名相同的才会被设置

        Args:
            info_dict (Dict[str, Any]): ServerInfo实例属性的字典

        Returns:
            ServerInfo: 返回生成的实例
        """
        ret = ServerInfo()
        for key, value in info_dict.items():
            if key in ret.__dict__:
                setattr(ret, key, value)
        return ret
        
class Option:
    '''选项类，用于描述选项信息
    '''
    def __init__(self, name:str, value:Any, description:str='', check:Callable[[str], Any]=None) -> None:
        self.__name = name
        self.__description = description
        self.__check:Callable[[str], Any] = (lambda x:x) if check is None else check
        self.__value = None
        self.set_value(value)

    @property
    def value(self)->Any:
        return self.__value
    
    @property
    def name(self)->str:
        return self.__name

    @property
    def description(self)->str:
        return self.__description
    
    def set_value(self, value:Any):
        """设置选项值

        Args:
            value (Any): 选项值

        Raises:
            ValueError: 校验失败则会抛出该异常

        Returns:
            Union[ValueError, None]: 失败则返回值检查的异常，成功返回None
        """
        self.__value = self.check(value)
    
    def check(self, value:Any)->Any:
        """检查值是否合法

        Args:
            value (Any): 需要校验的值

        Raises:
            ValueError: 校验失败则会抛出该异常

        Returns:
            Any: 校验通过的值的正确形式
        """
        try:
            value = self.__check(value)
        except BaseException as e:
            raise ValueError(e)
        return value

class SessionOptions:
    '''session实例使用的选项
    '''

    def __init__(self) -> None:
        self.__options:Dict[str, Option] = {}
        self.add_option('target', 'http://xxx.com/1.php', 'webshell连接地址')
        self.add_option('encoding', 'utf8', '默认编码')
        self.add_option('editor', 'vim', '默认文本编辑器')
        self.add_option('timeout', 30, '请求超时时间', float)
        self.add_option('preferred_session_type', SessionType.PHP.name, '首选session类型')
        self.add_option('wrapper_id', '', 'payload包装器ID')
        self.add_option('code_executor_id', '', '代码执行器ID')
        self.add_option('command_executor_id', '', '命令执行器ID')

    def get_option(self, name:str)->Union[Option, None]:
        """获取指定选项的值

        Args:
            name (str): 选项名

        Returns:
            Union[Option, None]: 选项对象，找不到返回None
        """
        return self.__options.get(name)

    def del_option(self, name:str)->bool:
        """删除指定选项

        Args:
            name (str): 选项名称

        Returns:
            bool: 成功返回True，否则False
        """
        return self.__options.pop(name, None) is not None

    def add_option(self, name:str, value:Any, description:str, check:Callable[[str], Any]=None):
        """添加一个新选项，可能会覆盖旧的

        Raises:
            ValueError: 校验失败则会抛出该异常

        Args:
            name (str): 选项名称，若存在同名选项则会覆盖
            value (Any): 选项的默认值
            description (str): 选项的描述
            check (Callable[[str], Any]): 类型检查的可调用对象,若为None，则不对选项进行类型检查
        """
        self.__options[name] = Option(name, value, description, check)

    def copy(self):
        """返回一个当前实例的副本

        Returns:
            SessionOptions: 当前实例的副本
        """
        return copy.deepcopy(self)

    @property
    def options_map(self)->Dict[str, Option]:
        '''获得所有选项字典
        '''
        return self.__options


class AdditionalData(dict):
    '''实现session的额外数据类
    '''
    def __init__(self) -> None:
        self.prompt:Callable[[], str] = lambda :'$ ' #命令提示符
