from typing import List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, CodeExecutor, colour, tablor, SessionType,logger, Option, Wrapper, CommandExecutor
import argparse, re, copy
from api.maintype.info import SessionOptions
from src.core.sessionadapter import SessionAdapter
from src.console.sessionmanager import ManagerSession
from src.core.pluginmanager import plugin_manager
import src.config as config
import re

def get_plugin_class():
    return OptionManagerPlugin

changeless_options = ('preferred_session_type', 'code_executor_id', 'wrapper_id') #session中无法修改的选项

class OptionManagerPlugin(Plugin):
    name = 'option manager'
    description = '管理当前session的设置信息'

    def __init__(self):
        pass

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def on_loaded(self):
        set_command = SetCommand(self.session)
        self.session.register_command(ShowCommand(self.session))
        self.session.register_command(set_command)
        self.session.register_complete_func(set_command.complete_ce)
        self.session.register_complete_func(set_command.complete)

        if isinstance(self.session, ManagerSession):
            self.session.additional_data['options_cache'] = {}#代码执行器选项缓存

class SetCommand(Command):

    description = '设置当前session的选项'
    command_name = 'set'
    command_type = CommandType.CORE_COMMAND

    def __init__(self, session:SessionAdapter) -> None:
        self.session = session

        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('name', help="选项名")
        self.parse.add_argument('value', help="选项值")
        self.help_info = self.parse.format_help()

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        name = args.name
        value = args.value

        if not isinstance(self.session, ManagerSession) and name in changeless_options:
            logger.error(f'这些选项无法在session中改变！')
            return CommandReturnCode.FAIL

        if name == 'code_executor_id':# 若是设置代码执行器，则特殊对待
            return self.select_code_executor(value)
        try:
            o = self.session.options.get_option(name)
            if o is None:
                logger.error(f"选项`{name}`不存在！")
                return CommandReturnCode.FAIL
            if name == 'command_executor_id' and not isinstance(self.session, ManagerSession):
                self.session.set_default_exec(value)
            else:
                o.set_value(value)
            logger.info(f"{name} => {value}", True)
        except ValueError as e:
            logger.error(e)
            return CommandReturnCode.FAIL
        return CommandReturnCode.SUCCESS
    
    def select_code_executor(self, ID:str)->CommandReturnCode:
        """选中一个代码执行器

        Args:
            ID (str): 代码执行器
        """
        ce = plugin_manager.plugins_map.get(ID)
        if ce is None or not issubclass(ce, CodeExecutor):
            logger.error(f'代码执行器`{ID}`没找到！')
            return CommandReturnCode.FAIL
        
        st = SessionType[self.session.options.get_option('preferred_session_type').value.upper()]
        if st not in ce.supported_session_types:
            logger.error(f"代码执行器不支持session类型`{st.name}`")
            return CommandReturnCode.FAIL

        self.session.config.session_type = SessionType[self.session.options.get_option('preferred_session_type').value]
        options_cache = self.session.additional_data.get('options_cache')
        tmp_options = {}
        old_ce:Type[Plugin] = plugin_manager.plugins_map.get(self.session.options.get_option('code_executor_id').value)
        if old_ce and old_ce.plugin_id in options_cache: # 清除当前session中上一个代码执行器附加的选项，并将选项值更新到缓存
            for o in options_cache[old_ce.plugin_id].values():
                o.set_value(self.session.options.options_map.get(o.name).value)
                self.session.options.del_option(o.name)
        if ID in options_cache:#若缓存中存在对应执行器的选项则加载缓存
            tmp_options = options_cache[ID]
        else:
            tmp_options = {n:Option(n, *v) for n, v in ce.options.items()}
            options_cache[ID] = tmp_options

        for n, o in tmp_options.items():
            self.session.options.add_option(n, o.value, o.description, o.check)
        
        self.session.options.get_option('code_executor_id').set_value(ID)
        self.session.additional_data.prompt = lambda :colour.colorize(config.app_name, ['bold', 'underline'])+f"({colour.colorize(ID, 'bold', fore='red')})> "
        return CommandReturnCode.SUCCESS

    def complete_ce(self, text:str)->List[str]:
        """补全code_executor_id, wrapper_id, command_executor_id的设置值

        Args:
            text (str): 传入的命令行字符串

        Returns:
            List[str]: 候选列表
        """
        matchs = []
        m = re.match(r'(set code_executor_id |set wrapper_id |set command_executor_id )(\S*)$', text, re.I)
        if m is None:
            return matchs
        ID = m.group(2).lower()
        t = Plugin
        if m.group(1) == 'set code_executor_id ':
            t = CodeExecutor
        elif m.group(1) == 'set wrapper_id ':
            t = Wrapper
        elif m.group(1) == 'set command_executor_id ':
            t = CommandExecutor
        
        for p in plugin_manager.get_plugin_list(t):
            ce:Plugin = p
            if ce.plugin_id.lower().startswith(ID):
                matchs.append(m.group(1)+ce.plugin_id+' ')
        return matchs

    def complete(self, text:str)->List[str]:
        """补全set命令

        Args:
            text (str): 传入的命令行字符串

        Returns:
            List[str]: 候选列表
        """
        matchs = []
        m = re.match(r'(set )([\w_]*)$', text, re.I)
        if m is None:
            return matchs
        name = m.group(2).lower()
        for n in self.session.options.options_map.keys():
            if n.lower().startswith(name):
                matchs.append(m.group(1)+n+' ')
        return matchs


class ShowCommand(Command):

    description = "显示session信息"
    command_name = 'show'
    command_type = CommandType.CORE_COMMAND

    def __init__(self, session:SessionAdapter) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('option', help="信息类型", choices=['options'], nargs='?', default='options')
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
        table = [['选项名', '值', '描述']]
        for name, v in self.session.options.options_map.items():
            if name in changeless_options and not isinstance(self.session, ManagerSession):
                name = colour.colorize(name, ['bold', 'invert'])
            value = v.value
            des = v.description
            table.append([name, value, des])
        print(tablor(table, border=False))


