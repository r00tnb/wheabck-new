'''插件如何编写payload在该文件定义
'''
from logging import setLoggerClass
import re
import base64
from typing import Any, Dict, Tuple

from .info import SessionType
from .utils import random_str, del_note_1

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
    '''C# payload执行规则
        输入：C#源代码，必须实现一个含有run静态方法的Payload类。其中vars为参数字典
            public class Payload {
                public static string run(Dictionary<string, object> vars) {}
            }
        输出：run()函数的返回值
        入口：ExecPayload类的静态方法call_run()为入口函数,返回值即为run函数的返回值，代码执行器可以无参调用该函数，格式如下
            public ExecPayload {
                public static string call_run() {
                    return Payload.run(vars);
                }
            }
    '''
    
    wrapper_code = r'''
    import System.Collections.Generic;

    %(code)s

    public class ExecPayload {
        public static string call_run() {
            %(vars)s
            return Payload.run(vars);
        }
    }
    '''

    @property
    def code(self)-> bytes:
        result = self._code

        # 删除所有注释
        result = del_note_1(result).decode()

        vars = 'Dictionary<string, object> vars = new Dictionary<string, object>();'
        for k, v in self._global.items():
            t, v = self.python_to_cs(v)
            vars += f'vars.Add("{k}", {v});'

        result = CSharpPayload.wrapper_code % {'code':result, 'vars':vars}

        return result.encode()
    
    def python_to_cs(self, var)-> tuple:
        '''将python变量映射到C#变量
        '''
        if var is None:
            return 'object', "null"
        elif var is True:
            return 'bool', "true"
        elif var is False:
            return 'bool', "false"
        elif isinstance(var, int):
            return 'int', str(var)
        elif isinstance(var, float):
            return 'double', str(var)
        elif isinstance(var, str):
            var = base64.b64encode(var.encode()).decode()
            return 'string', f'System.Text.Encoding.UTF8.GetString(System.Convert.FromBase64String("{var}"))'
        else: # 其他情况当字节流处理，并且对字符串进行编码，防止解析错误
            if not isinstance(var, bytes):
                var = str(var).encode()
            var = base64.b64encode(var).decode()
            return 'byte[]', f'System.Convert.FromBase64String("{var}")'

class PHPPayload(Payload):
    '''PHP payload执行规则
        输入：php代码，必须包含一个run函数，格式如下。其中vars为Payload参数字典
            function run(array vars):str
        输出：run()函数的返回值
        入口：call_run()函数为入口函数,返回值即为run函数的返回值，代码执行器可以无参调用该函数，格式如下
            function call_run(){
                return run(vars)
            }
    '''
    wrapper_code = r'''
    %(code)s
    function call_run(){
        %(vars)s
        return run($vars);
    }
    '''

    @property
    def code(self)-> bytes:
        # 删除所有注释
        result = del_note_1(self._raw_payload)

        # 删除标签和开始结尾的空白符
        result = re.sub(r'^\s*<\?php\s*|\s*\?>\s*$', '', result.decode(errors='ignore'))

        # 添加参数
        vars = '$vars = array();'
        for k, v in self._vars.items():
            vars += f'$vars["{k}"] = {self.python_to_php(v)};'
        result = PHPPayload.wrapper_code % {'vars':vars, 'code':result}

        return result.encode()

    
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