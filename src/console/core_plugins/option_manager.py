from typing import List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, CodeExecutor, colour, tablor, SessionType,logger
import argparse, re, copy
from api.maintype.info import SessionOptions
from src.core.sessionadapter import SessionAdapter
from src.console.sessionmanager import ManagerSession
from src.core.pluginmanager import plugin_manager
import src.config as config
import re

def get_plugin_class():
    return OptionManagerPlugin

class OptionManagerPlugin(Plugin):
    name = 'option manager'
    description = 'Manage the option information of the current session'

    def __init__(self):
        pass

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def on_loaded(self):
        set_command = SetCommand(self.session)
        self.session.register_command(ShowCommand(self.session))
        self.session.register_command(set_command)
        self.session.register_complete_func(set_command.complete)

        if isinstance(self.session, ManagerSession):
            self.session.additional_data['options_cache'] = {}#代码执行器选项缓存

class SetCommand(Command):

    description = 'Change the option value of the current session'

    def __init__(self, session:SessionAdapter) -> None:
        self.session = session

        self.parse = argparse.ArgumentParser(prog='set', description=self.description)
        self.parse.add_argument('name', help="Ooption name")
        self.parse.add_argument('value', help="Options value")
        self.help_info = self.parse.format_help()

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        name = args.name
        value = args.value

        if not isinstance(self.session, ManagerSession) and name in ('preferred_session_type', 'code_executor_id'):
            logger.error(f'This option cannot be changed in current session')
            return CommandReturnCode.FAIL

        if name == 'code_executor_id':# 若是设置代码执行器，则特殊对待
            return self.select_code_executor(value)

        if self.session.options.set_option(name, value):
            if name == 'code_executor_id':
                if self.select_code_executor(value) == CommandReturnCode.FAIL:
                    return CommandReturnCode.FAIL
            logger.info(f"{name} => {value}", True)
            return CommandReturnCode.SUCCESS
        else:
            logger.error(f"Option `{name}` is not exists")
            return CommandReturnCode.FAIL
    
    def select_code_executor(self, ID:str)->CommandReturnCode:
        """选中一个代码执行器

        Args:
            ID (str): 代码执行器
        """
        ce = plugin_manager.plugins_map.get(ID)
        if ce is None or not issubclass(ce, CodeExecutor):
            logger.error(f'Code executor not found with ID `{ID}`')
            return CommandReturnCode.FAIL
        
        st = SessionType[self.session.options.get_option('preferred_session_type').upper()]
        if st not in ce.supported_session_types:
            logger.error(f"The code executor does not support the current session type `{st.name}`")
            return CommandReturnCode.FAIL

        self.session.config.session_type = SessionType[self.session.options.get_option('preferred_session_type')]
        options_cache = self.session.additional_data.get('options_cache')
        tmp_options = {}
        old_ce:Type[Plugin] = plugin_manager.plugins_map.get(self.session.options.get_option('code_executor_id'))
        if old_ce and old_ce.plugin_id in options_cache: # 清除当前session中上一个代码执行器附加的选项，并将选项值保存到缓存
            for n in options_cache[old_ce.plugin_id]:
                options_cache[old_ce.plugin_id][n] = self.session.options.options_map.get(n)
                self.session.options.del_option(n)
        if ID in options_cache:#若缓存中存在对应执行器的选项则加载缓存
            tmp_options = options_cache[ID]
        else:
            tmp_options = ce.options
            options_cache[ID] = copy.deepcopy(ce.options)

        for n, v in tmp_options.items():
            self.session.options.add_option(n, v[0], v[1])
        
        self.session.options.set_option('code_executor_id', ID)
        self.session.additional_data.prompt = lambda :colour.colorize(config.app_name, ['bold', 'underline'])+f"({colour.colorize(ID, 'bold', fore='red')})> "
        return CommandReturnCode.SUCCESS

    def complete(self, text:str)->List[str]:
        """补全set命令

        Args:
            text (str): 传入的命令行字符串

        Returns:
            List[str]: 候选列表
        """
        matchs = []
        m = re.match(r'(set )([\w_]*)', text, re.I)
        if m is None:
            return matchs
        name = m.group(2).lower()
        for n in self.session.options.options_map.keys():
            if n.lower().startswith(name):
                matchs.append(m.group(1)+n+' ')
        return matchs

    @property
    def command_name(self) -> str:
        return 'set'

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND


class ShowCommand(Command):

    description = "Displays the current session option information"

    def __init__(self, session:SessionAdapter) -> None:
        self.parse = argparse.ArgumentParser(prog='show', description=self.description)
        self.parse.add_argument('option', help="Information type", choices=['options'], nargs='?', default='options')
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.option:#显示session参数信息
            self.show_options()
        else:
            print(self.help_info)
        return CommandReturnCode.FAIL

    def show_options(self):
        table = [['Name', 'Value', 'Description']]
        for name, v in self.session.options.options_map.items():
            value, des = v
            table.append([name, value, des])
        print(tablor(table, border=False))

    @property
    def command_name(self) -> str:
        return 'show'

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND