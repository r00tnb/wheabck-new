from api import Plugin, colour, Session
import time

def get_plugin_class():
    return PromptTimePlugin

class PromptTimePlugin(Plugin):

    name = 'prompt_time'
    description = '为命令提示符添加时间显示'

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def on_loaded(self):
        p = self.session.additional_data.prompt
        self.session.additional_data.prompt = lambda :colour.colorize(time.ctime(), 'note')+' '+p()