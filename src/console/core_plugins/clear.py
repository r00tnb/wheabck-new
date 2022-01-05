from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session
import argparse, os, platform

def get_plugin_class():
    return ClearPlugin

class ClearPlugin(Plugin, Command):
    name = 'clear'
    description = '清空控制台输出'
    command_name = 'clear'
    command_type = CommandType.CORE_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        if platform.system().startswith('Windows'):
            os.system('cls')
        else:
            os.system('clear')
        return CommandReturnCode.SUCCESS