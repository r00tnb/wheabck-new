from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session
import argparse, os, platform

def get_plugin_class():
    return ClearPlugin

class ClearPlugin(Plugin, Command):
    name = 'lrun'
    description = 'Run local system commands'

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.parse.add_argument('cmd', help="Local system command")
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        os.system(args.cmd)
        return CommandReturnCode.SUCCESS

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND