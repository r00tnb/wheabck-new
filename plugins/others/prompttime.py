from os import pardir
from api import Plugin, colour, Session, Command, CommandType, CommandReturnCode, Cmdline
import time, argparse

def get_plugin_class():
    return PromptTimePlugin

class PromptTimePlugin(Plugin, Command):

    name = 'prompt_time'
    description = '为命令提示符添加时间显示'
    command_name = 'prompt_time'
    command_type = CommandType.MISC_COMMAND

    def __init__(self):
        self.raw_prompt = None
        self.on = True
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('state', help="是否开启", choices=['on', 'off'])
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def my_prompt(self):
        if self.on:
            return colour.colorize(time.strftime("%Y年%m月%d日 %H时%M分%S秒", time.localtime()), 'invert')+' '+self.raw_prompt()
        else:
            return self.raw_prompt()

    def on_loaded(self):
        self.raw_prompt = self.session.additional_data.prompt
        self.session.additional_data.prompt = self.my_prompt


    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        self.on = args.state == 'on'
        return CommandReturnCode.SUCCESS