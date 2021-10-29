
from api import Session, logger, Command, CommandReturnCode, CommandType, Plugin, Cmdline
import argparse
import base64
import tempfile
import os

def get_plugin_class():
    return NotepadPlugin

class NotepadPlugin(Plugin, Command):
    name = '笔记本'
    description = '针对当前连接记录一些笔记或备注'
    command_name = 'notepad'
    command_type = CommandType.MISC_COMMAND

    def __init__(self):
        super().__init__()
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('editor', help="指定编辑器路径用于打开笔记本，默认使用session配置中的编辑器", nargs='?', default=None)
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, args: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(args.options)
        editor = args.editor
        if editor is None:
            editor = self.session.options.get_option('editor').value
        
        data = self.session.load_json(self.command_name)
        if data:
            data = base64.b64decode(data.get('data','').encode())
        else:
            data = b''

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'note')
            with open(path, 'wb') as f:
                f.write(data)

            if os.system(f"{editor} {path}") != 0:
                logger.error(f"运行编辑器`{editor}`失败!编辑器必须要像`vim filename`或者`notepad filename`这样能在控制台中执行")
                return CommandReturnCode.FAIL
            with open(path, 'rb') as f:
                new_data = f.read()
            if data == new_data:
                logger.warning('内容未更改!')
            else:
                if self.session.save_json(self.command_name, {'data':base64.b64encode(new_data).decode()}):
                    logger.info("笔记内容已更新!", True)
                else:
                    logger.error('笔记内容更新失败！')
                    return CommandReturnCode.FAIL
        return CommandReturnCode.SUCCESS
