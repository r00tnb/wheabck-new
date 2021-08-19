import abc
from typing import Any, Dict, List, Tuple, Union
from .maintype.info import SessionType, ServerInfo

class CodeExecutor(metaclass=abc.ABCMeta):
    '''代码执行器，用于在远程服务器执行任意代码
    '''

    # 返回代码执行器需要使用的额外参数字典(这些参数将会添加到session options选项中),额外参数字典,键为参数名，值为一个列表，其中第一项为默认值，第二项为该参数的描述信息
    options:Dict[str, Tuple[Any, str]] = {}
    
    @abc.abstractmethod
    def get_server_info(self)->Union[ServerInfo, None]:
        """获取远程服务器基本信息，成功返回服务端基本信息，失败返回None

        Returns:
            Union[ServerInfo, None]: 服务器基本信息对象，失败则为None
        """


    @abc.abstractmethod
    def generate(self, config: Dict[str, Any]={}) -> bytes:
        """生成webshell服务端文件

        Args:
            config (Dict[str, Any], optional): 若webshell需要根据参数来配置，可通过该参数传入. Defaults to {}.

        Returns:
            bytes: 返回最终生成的webshell字节流
        """


    @abc.abstractmethod
    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        """向目标URL发送payload执行请求并获取执行结果

        Args:
            payload (bytes): payload的字节流
            timeout (float): 本次payload的执行中请求的超时时间，为0时则无限等待（这是一个约定，实现该方法时应该实现此特性）

        Returns:
            Union[bytes, None]: 返回payload在目标上的执行结果,失败则返回None
        """


class CommandExecutor(metaclass=abc.ABCMeta):
    '''命令执行器，用于在远程服务器执行命令，一般它依赖代码执行器
    '''

    @abc.abstractmethod
    def exec(self, cmd:bytes)->Union[bytes, None]:
        """在远程服务器执行命令并返回命令执行结果

        Args:
            cmd (bytes): 合法的命令字节流

        Returns:
            Union[bytes, None]: 命令执行结果， 失败返回None
        """