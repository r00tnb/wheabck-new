from api import CommandReturnCode, Command, Cmdline, CommandType, Session
import argparse

class AEManage(Command):
    name = 'ae_manage'

    def __init__(self, session:Session) -> None:
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.help_info = self.parse.format_help()

        self.session = session
    
    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        return CommandReturnCode.SUCCESS

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.MISC_COMMAND