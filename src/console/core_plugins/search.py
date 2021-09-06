from typing import List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, CodeExecutor, colour, tablor, Wrapper, CommandExecutor
import argparse, re
from src.console.sessionmanager import ManagerSession
from src.core.pluginmanager import plugin_manager
import src.config as config
import re

def get_plugin_class():
    return SearchPlugin

class SearchPlugin(Plugin, Command):
    name = 'search'
    description = '搜索可用的插件'
    command_name = 'search'
    command_type = CommandType.CORE_COMMAND

    manager_session:ManagerSession # 保存session管理者实例

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('keywords', help="要搜索的关键字列表，可以是插件ID、名称、简单描述、类型中的关键字", nargs='*')
        self.parse.add_argument('-e', help="只搜索代码执行器插件", action='store_true')
        self.parse.add_argument('-w', help="只搜索payload包装器插件", action='store_true')
        self.parse.add_argument('-s', help="只搜索远程命令执行插件", action='store_true')
        self.parse.add_argument('-c', help="只搜索命令插件，可指定插件分类", choices=[t.name for t in list(CommandType)], nargs='*')
        self.help_info = self.parse.format_help()

        self._complete_cache:List[str] = []

    def on_loading(self, session: Session) -> bool:
        if isinstance(session, ManagerSession):
            SearchPlugin.manager_session = session
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        return self.search(args.keywords, args.e, args.w, args.s, args.c)

    def search(self, keywords_list:List[str], only_cs:bool, only_wrapper:bool, 
        only_command_exec:bool, command_type_list:List[CommandType])->CommandReturnCode:
        '''查找合适的插件,并输出
        '''
        keywords_list = [k.lower() for k in keywords_list if k]
        if not keywords_list:
            keywords_list = ['']
        last_search_results:List[Type[Plugin]] = []

        def s(plugin_class:Type[Plugin])->bool:
            '''查找关键字
            '''
            for k in keywords_list:
                if k in plugin_class.description.lower() or k in plugin_class.name.lower() or k in plugin_class.plugin_id.lower():
                    return True
                for t in plugin_class.supported_session_types:
                    if k in t.name.lower():
                        return True
            return False

        for plugin_class in plugin_manager.plugins_map.values():
            if only_cs and not issubclass(plugin_class, CodeExecutor):
                continue
            if only_wrapper and not issubclass(plugin_class, Wrapper):
                continue
            if only_command_exec and not issubclass(plugin_class, CommandExecutor):
                continue
            if command_type_list and not (issubclass(plugin_class, Command) and plugin_class.command_type.name in command_type_list):
                continue
            if s(plugin_class):
                last_search_results.append(plugin_class)

        sl = [['Plugin ID', 'Type', 'Name', 'Description']]
        color_reg = [{
            'regexp': r"(?i)"+'|'.join([re.escape(k) for k in keywords_list]),
            'color': ['bold', 'red', '']
        }]
        cc = colour if keywords_list!=[''] else lambda x,y:x
        for plugin_class in last_search_results:
            sl.append([cc(plugin_class.plugin_id, color_reg), 
                cc(', '.join([t.name for t in plugin_class.supported_session_types]), color_reg), 
                cc(plugin_class.name, color_reg), 
                cc(plugin_class.description, color_reg)])
        print(tablor(sl, True, False, title="Search Result"))
        return CommandReturnCode.SUCCESS