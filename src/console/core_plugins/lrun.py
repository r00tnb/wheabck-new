from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session
import argparse, os, platform

def get_plugin_class():
    return ClearPlugin

class ClearPlugin(Plugin, Command):
    name = 'lrun'
    description = 'Run local system commands'
    command_name = 'lrun'
    command_type = CommandType.CORE_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('cmd', help="Local system command")
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        os.system(args.cmd)
        return CommandReturnCode.SUCCESS