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

@enum.unique
class CommandType(enum.Enum):
    '''命令类型，预定义命令类型用于给命令分类
    '''
    CORE_COMMAND = enum.auto() # 核心命令，一般为自带的命令
    SYSTEM_COMMAND = enum.auto() # 用于在目标系统执行基础操作的命令，如命令执行、代码执行等
    FILE_COMMAND = enum.auto() # 用于文件操作的命令
    MISC_COMMAND = enum.auto() # 杂项命令
    POST_COMMAND = enum.auto() # 后渗透命令

@enum.unique
class OSType(enum.Enum):
    '''定义服务器操作系统类型
    '''
    UNIX = enum.auto() # Unix类型
    WINDOWS = enum.auto() # Windows类型
    OSX = enum.auto() # mac osx类型
    OTHER = enum.auto() # 其他类型

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
        

class SessionOptions:
    '''session实例使用的选项
    '''
    def __init__(self) -> None:
        self.__options:Dict[str, List[Any, str]] = {# session的选项字典， 键为选项名， 值的第一项为选项值，第二项为该选项的描述
            'target':['http://xxx.com/1.php', "An HTTP link to the target"],# webshell的url地址
            'encoding':['utf8', 'The encoding used by the current session'],# 默认编码
            'timeout':[30, 'HTTP request timeout (in seconds). If it is set to 0, it will wait indefinitely'],# 每次请求的超时时间，单位秒，设置为0则表示无限等待请求完成
            'preferred_session_type':[SessionType.PHP.name, f"Preferred session type, like {','.join([t.name for t in list(SessionType)])}"], # 首选session类型，一般指定当前session的类型 
            'wrapper_id':['', 'Current payload wrapper ID'],# 使用的payload包装器id,当为None时则不使用包装器
            'code_executor_id':['', 'Current code executor ID'],# 使用的代码执行器id，必须是有效的id否则session不会创建成功
            'command_executor_id':['', 'Current command executor ID'], # 当前的命令执行器id， 当为None时则表示无命令执行器
        }

    def get_option(self, name:str)->Union[Any, None]:
        """获取指定选项的值和描述信息

        Args:
            name (str): 选项名

        Returns:
            Union[Any, None]: 选项值，找不到返回None
        """
        for n, v in self.__options.items():
            if n == name:
                return v[0]
        return None

    def set_option(self, name:str, value:Any)->bool:
        """设置选项的值

        Args:
            name (str): 选项名称
            value (Any): 要设置的值(值必须是简单类型)

        Returns:
            bool: 成功返回True，失败返回False(一般是选项不存在)
        """
        for n, v in self.__options.items():
            if n==name:
                v[0] = value
                return True
        return False

    def del_option(self, name:str)->bool:
        """删除指定选项

        Args:
            name (str): 选项名称

        Returns:
            bool: 成功返回True，否则False
        """
        return self.__options.pop(name, None) is not None

    def add_option(self, name:str, value:Any, description:str):
        """添加一个新选项，可能会覆盖旧的

        Args:
            name (str): 选项名称，若存在同名选项则会覆盖
            value (Any): 选项的默认值
            description (str): 选项的描述
        """
        self.__options[name] = [value, description]

    def copy(self):
        """返回一个当前实例的副本

        Returns:
            SessionOptions: 当前实例的副本
        """
        return copy.deepcopy(self)

    @property
    def options_map(self)->Dict[str, Tuple[Any, str]]:
        '''获得所有选项字典的一个副本
        '''
        return copy.deepcopy(self.__options)


class AdditionalData(dict):
    '''实现session的额外数据类
    '''
    def __init__(self) -> None:
        self.prompt:Callable[[], str] = lambda :'$ ' #命令提示符
