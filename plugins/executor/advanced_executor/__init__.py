from typing import Any, Dict, Union
from api import Plugin, Session, CodeExecutor, ServerInfo, OSType, Command
import json, base64
from .manage_command import AEManage

def get_plugin_class():
    return AdvancedExecutor

class AdvancedExecutor(Plugin, CodeExecutor, Command):
    name = "高级代码执行器"
    description = '可以进行扩展的代码执行器'
    options = {'editor':['vim', '编辑器']}

    def __init__(self):
        self.manage:AEManage = None

    def on_loading(self, session: Session) -> bool:
        self.manage = AEManage(session)
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

    def eval(self, payload: bytes, timeout: float) -> Union[bytes, None]:
        return super().eval(payload, timeout)

    def generate(self, config: Dict[str, Any]) -> bytes:
        return super().generate(config=config)

        