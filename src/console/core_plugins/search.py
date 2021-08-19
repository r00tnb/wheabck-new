from typing import List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, CodeExecutor, colour, tablor, Wrapper
import argparse, re
from src.console.sessionmanager import ManagerSession
from src.core.pluginmanager import plugin_manager
import src.config as config
import re

def get_plugin_class():
    return SearchPlugin

class SearchPlugin(Plugin, Command):
    name = 'search'
    description = 'search plugins you currently need to use'

    manager_session:ManagerSession # 保存session管理者实例

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.parse.add_argument('keywords', help="Keywords of plugin, such as name, description, type, etc", nargs='*')
        self.parse.add_argument('-e', help="Search only code executor plugins", action='store_true')
        self.parse.add_argument('-w', help="Search only payload wrapper plugins", action='store_true')
        self.parse.add_argument('-c', help="Search only command plugins", action='store_true')
        self.help_info = self.parse.format_help()

        self._complete_cache:List[str] = []

    def on_loading(self, session: Session) -> bool:
        if isinstance(session, ManagerSession):
            SearchPlugin.manager_session = session
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        return self.search(args.keywords, args.e, args.w, args.c)

    def search(self, keywords_list:List[str], only_cs:bool, only_wrapper:bool, only_command:bool)->CommandReturnCode:
        '''查找合适的插件,并输出
        '''
        keywords_list = [k.lower() for k in keywords_list if k]
        if not keywords_list:
            keywords_list = ['']
        last_search_results:List[Type[Plugin]] = []

        def s(plugin_class:Type[Plugin])->bool:
            for k in keywords_list:
                if k in plugin_class.description.lower() or k in plugin_class.name.lower() or k in plugin_class.plugin_id.lower():
                    return True
                for t in plugin_class.supported_session_types:
                    if k in t.name.lower():
                        return True
            return False

        for plugin_class in plugin_manager.plugins_map.values():
            if only_command and not issubclass(plugin_class, Command):
                continue
            if only_cs and not issubclass(plugin_class, CodeExecutor):
                continue
            if only_wrapper and not issubclass(plugin_class, Wrapper):
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

    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND
