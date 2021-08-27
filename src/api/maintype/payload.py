'''插件如何编写payload在该文件定义
'''
import re
import base64
from typing import Any, Dict, Tuple

from .info import SessionType
from .utils import random_str

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
        参数：全局类Globals的静态属性
        输入：C#源代码，必须实现一个含有run静态方法的Payload类。
            public class Payload {
                public static string run() {}
            }
        输出：run()函数的返回值
    '''
    
    wrapper_code = r'''%(code)s

    public static class Globals{
        %(var)s

        public static string json_encode(object obj){
            System.Runtime.Serialization.Json.DataContractJsonSerializer js = new System.Runtime.Serialization.Json.DataContractJsonSerializer(obj.GetType());
            System.IO.MemoryStream msObj = new System.IO.MemoryStream();
            js.WriteObject(msObj, obj);
            msObj.Position = 0;
            System.IO.StreamReader sr = new System.IO.StreamReader(msObj, System.Text.Encoding.UTF8);
            string json = sr.ReadToEnd();
            sr.Close();
            msObj.Close();
            return json;
        }
    }
    '''

    @property
    def code(self)-> bytes:
        result = self._code

        # 删除所有注释
        result = PHPPayload.del_note(result).decode()

        cs_global = ''
        for k, v in self._global.items():
            t, v = self.python_to_cs(v)
            cs_global += f"public static {t} {k}={v};\n"

        result = CSharpPayload.wrapper_code % {'code':result, 'var':cs_global}

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
        return run(array(%(vars)s));
    }
    '''

    @property
    def code(self)-> bytes:
        # 删除所有注释
        result = self.del_note(self._raw_payload)

        # 删除标签和开始结尾的空白符
        result = re.sub(r'^\s*<\?php\s*|\s*\?>\s*$', '', result.decode(errors='ignore'))

        # 添加参数
        vars = []
        for k, v in self._vars.items():
            vars.append(f'"{k}"=>{self.python_to_php(v)}')
        result = PHPPayload.wrapper_code % {'vars':','.join(vars), 'code':result}

        return result.encode()
    
    @classmethod
    def del_note(cls, code:bytes)->bytes:
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