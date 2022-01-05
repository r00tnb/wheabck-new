from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session
import argparse, os

def get_plugin_class():
    return ExitPlugin

class ExitPlugin(Plugin, Command):
    name = 'exit'
    description = 'Exit command'
    command_name = 'exit'
    command_type = CommandType.CORE_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('-y', help="退出而不询问", action="store_true")
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if not args.y and input('确定退出吗?(y/n) ').lower() != 'y':
            return CommandReturnCode.FAIL
        return CommandReturnCode.EXIT