import abc
from typing import Any, Callable, Dict, List, Tuple, Union
from .maintype.info import SessionType, ServerInfo, Option

class CodeExecutor(metaclass=abc.ABCMeta):
    '''代码执行器，用于在远程服务器执行任意代码
    '''

    # 返回代码执行器需要使用的额外参数字典(这些参数将会添加到session options选项中),额外参数字典,
    # 键为参数名，值为一个列表，其中第一项为默认值，第二项为该参数的描述信息, 第三项若有，应该为可调用对象用于对值进行检查
    options:Dict[str, Tuple[Any, str, Callable[[str], Any]]] = {}
    
    @abc.abstractmethod
    def get_server_info(self)->Union[ServerInfo, None]:
        """获取远程服务器基本信息，成功返回服务端基本信息，失败返回None

        Returns:
            Union[ServerInfo, None]: 服务器基本信息对象，失败则为None
        """


    @abc.abstractmethod
    def generate(self, config: Dict[str, str]={}) -> bytes:
        """生成webshell服务端文件

        Args:
            config (Dict[str, Any], optional): 额外选项字典，会覆盖代码执行器额外选项的默认值,必会传入键TYPE指定session类型. Defaults to {}.

        Returns:
            bytes: 返回最终生成的webshell字节流
        """


    @abc.abstractmethod
    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        """向目标URL发送payload执行请求并获取执行结果

        Args:
            payload (bytes): payload的字节流
            timeout (float): 本次payload的执行中请求的超时时间(单位秒)，为0时则无限等待，小于0则使用默认值（这是一个约定，实现该方法时应该实现此特性）

        Returns:
            Union[bytes, None]: 返回payload在目标上的执行结果,失败则返回None
        """


class CommandExecutor(metaclass=abc.ABCMeta):
    '''命令执行器，用于在远程服务器执行命令，一般它依赖代码执行器
    '''

    @abc.abstractmethod
    def exec(self, cmd:bytes, timeout:float)->Union[bytes, None]:
        """在远程服务器执行命令并返回命令执行结果

        Args:
            cmd (bytes): 合法的命令字节流
            timeout (float): 本次命令的执行超时时间(单位秒)，为0时则无限等待，小于0则使用默认值（这是一个约定，实现该方法时应该实现此特性）

        Returns:
            Union[bytes, None]: 命令执行结果， 失败返回None
        """