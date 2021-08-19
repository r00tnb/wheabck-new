from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session
import argparse, os, platform

def get_plugin_class():
    return ClearPlugin

class ClearPlugin(Plugin, Command):
    name = 'clear'
    description = 'Empty console'

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        if platform.system().startswith('Windows'):
            os.system('cls')
        else:
            os.system('clear')
        return CommandReturnCode.SUCCESS

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND