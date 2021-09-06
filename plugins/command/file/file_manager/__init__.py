from api import Plugin, Session

from .cat import CatCommand
from .cd import CdCommand
from .ls import LsCommand
from .cp import CpCommand
from .download import DownloadCommand
from .edit import EditCommand
from .mkdir import MkdirCommand
from .mv import MvCommand
from .rm import RmCommand
from .touch import TouchCommand
from .upload import UploadCommand

def get_plugin_class():
    return FileManager

class FileManager(Plugin):
    name = '文件管理器'
    description = '提供基本的文件管理功能'

    def __init__(self):
        pass

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def on_loaded(self):
        # 注册文件管理命令
        self.session.register_command(CatCommand(self.session))
        self.session.register_command(CdCommand(self.session))
        self.session.register_command(LsCommand(self.session))
        self.session.register_command(CpCommand(self.session))
        self.session.register_command(DownloadCommand(self.session))
        self.session.register_command(EditCommand(self.session))
        self.session.register_command(MkdirCommand(self.session))
        self.session.register_command(MvCommand(self.session))
        self.session.register_command(RmCommand(self.session))
        self.session.register_command(TouchCommand(self.session))
        self.session.register_command(UploadCommand(self.session))