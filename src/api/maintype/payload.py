import re
import base64
from typing import Any, Dict

from .info import SessionType

class Payload:
    '''封装payload

    :attr _raw_payload: 原始payload字节流
    :attr _vars: payload中可能使用的全局变量，具体如何使用取决于派生类
    '''

    def __init__(self, raw_payload:bytes,vars:Dict[str,Any]={}) -> None:
        self._raw_payload = raw_payload
        self._vars = vars
    
    @property
    def code(self)->bytes:
        '''返回payload的字节流

        :returns: bytes
        '''
        return self._raw_payload

    @classmethod
    def create_payload(cls, payload:bytes, vars:Dict[str,Any]={}, session_type:SessionType=SessionType.PHP):
        """获取一个payload实例

        Args:
            payload (bytes): payload的字节流
            vars (Dict[str,Any], optional): 传入payload的变量字典. Defaults to {}.
            session_type (SessionType, optional): payload对应的session类型. Defaults to SessionType.PHP.

        Returns:
            Payload: 根据session类型创建对应的payload实例
        """
        if session_type == SessionType.PHP:
            return PHPPayload(payload, vars)
        elif session_type == SessionType.ASP_NET_CS:
            return CSharpPayload(payload, vars)
        else:
            return Payload(payload, vars)

class CSharpPayload(Payload):
    pass

class PHPPayload(Payload):

    @property
    def code(self)-> bytes:
        # 删除所有注释
        result = self.del_note(self._raw_payload)

        # 删除标签和开始结尾的空白符
        result = re.sub(r'^\s*<\?php\s*|\s*\?>\s*$', '', result.decode(errors='ignore'))

        for k, v in self._vars.items():
            result = f"${k} = {self.python_to_php(v)};\n" + result

        return result.encode()
    
    def del_note(self, code:bytes)->bytes:
        '''删除php注释
        '''
        quotes = b"'\"`"
        length = len(code)
        end = 0
        result = b''
        quote = None
        while end<length:
            if code[end:end+1] in quotes:
                if quote is None:
                    quote = code[end:end+1]
                elif quote == code[end:end+1]:
                    quote = None
            elif quote is None and code[end:end+1] == b'/' and end<length-1:
                end += 1
                tmp = code[end:end+1]
                if tmp in b'/*':
                    end += 1
                    while end < length:
                        if code[end:end+1] == b'\n' and tmp == b'/': # 单行注释
                            end += 1
                            break
                        elif code[end:end+1] == b'*' and tmp == b'*' and end < length-1: # 多行注释
                            end += 1
                            if code[end:end+1] == b'/':
                                end += 1
                                break
                        end += 1
                else:
                    result += b'/'+tmp
                    end += 1
                continue
            result += code[end:end+1]
            end += 1
        return result

    
    def python_to_php(self, var):
        '''将python变量映射到PHP变量
        '''
        if var is None:
            return "null"
        elif var is True:
            return "true"
        elif var is False:
            return "false"
        elif isinstance(var, (int, float)):
            return str(var)
        else: # 其他情况当字符串处理，并且对字符串进行编码，防止解析错误
            if not isinstance(var, bytes):
                var = str(var).encode()
            var = base64.b64encode(var).decode()
            return f"base64_decode('{var}')"