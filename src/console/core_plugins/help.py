from typing import List, Union
from api import Cmdline, Session, Command, CommandReturnCode, Plugin, tablor, CommandType, logger
from src.core.sessionadapter import SessionAdapter
import argparse, re

def get_plugin_class():
    return HelperCommand

class HelperCommand(Plugin, Command):
    name = 'help'
    description = "Get command help information!"
    command_name = 'help'
    command_type = CommandType.CORE_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('cmd', help="A command name",  nargs='?')
        self.help_info = self.parse.format_help()

        self.session:SessionAdapter

    def on_loading(self, session: Session) -> bool:
        session.register_complete_func(self.complete)
        session.register_command(HelpAliasCommand(self))
        return super().on_loading(session)

    def all_info(self)->str:
        '''返回所有命令的简短信息
        '''
        cmd_info_map = {t:[['Name', 'Description']] for t in CommandType}
        ret = r'''
开始一个webshell连接：
    1.set target http://xxx.com/1.php
    2.set preferred_session_type PHP
    3.set code_executor_id executor/one_word
    4.使用set命令设置代码执行器的选项
    5.设置完毕后使用exploit命令开始一个交互式webshell管理控制台
快速开始：
    1.connections -c 1 （从一个已保存的连接开始webshell管理）

'''
        a, b, i = 0, 0, 0
        for p in self.session.command_map.values():
            if p.command_type == CommandType.CORE_COMMAND:
                i += 1
            cmd_info_map[p.command_type].append([p.command_name, p.description])
            if p.command_name == 'help':
                a = i
            elif p.command_name == '?':
                b = i
        tmp = cmd_info_map[CommandType.CORE_COMMAND]
        if a and b:
            tmp[1], tmp[b] = tmp[b], tmp[1]
            tmp[2], tmp[a] = tmp[a], tmp[2]
        
        for t, cmd_info in cmd_info_map.items():
            if len(cmd_info) == 1:
                continue
            title = ' '.join([i.capitalize() for i in t.name.split('_')])
            ret += tablor(cmd_info, border=False, title=title)
        return ret

    def get_cmd_help(self, cmd:str)->Union[str, None]:
        '''获得指定命令的帮助信息
        '''
        for p in self.session.command_map.values():
            if p.command_name == cmd:
                s = p.help_info
                if isinstance(p, Plugin):
                    s = f"Plugin ID: {p.plugin_id}\n"+s
                return s
        return None

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.cmd is not None:
            s = self.get_cmd_help(args.cmd)
            if s is None:
                logger.error(f'No command named `{args.cmd}`')
                return CommandReturnCode.FAIL
            else:
                print(s)
        else:
            print(self.all_info())
        return CommandReturnCode.SUCCESS


    def complete(self, text:str)->List[str]:
        '''自动补全已存在的命令
        '''
        matchs = []
        m = re.match(r'(help )(.*)', text, re.I)
        if m is None:
            return matchs
        cmd = m.group(2).lower()
        for p in self.session.command_map.values():
            if p.command_name.lower().startswith(cmd):
                matchs.append(m.group(1)+p.command_name+' ')
        return matchs

class HelpAliasCommand(Command):
    description = "This is an alias for `help`"
    command_name = '?'
    command_type = CommandType.CORE_COMMAND

    def __init__(self, help:HelperCommand) -> None:
        self.help = help

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        return self.help.run(cmdline)