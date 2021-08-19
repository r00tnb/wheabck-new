from src.api.maintype.info import SessionType
from src.api.executor import CodeExecutor
from src.api.command import Command
from src.core.connectionmanager import Connection
from src.core.sessionadapter import SessionAdapter
from typing import Callable, Dict, List, Type, Union
from src.api.session import Session
from src.api.ui.color import colour
from src.api.ui.logger import logger
from src.core.pluginmanager import plugin_manager
import src.config as config

__all__ = ['ManagerSession']

myconn = Connection()

class ManagerSession(SessionAdapter):
    '''用于管理当前信息的session
    '''
    def __init__(self) -> None:
        super().__init__(myconn, False)
        self.__session_map:Dict[str, SessionAdapter] = {} # 保存当前存活的session,键为session id值为session对象
        self.__current_session_id:str = None # 当前使用的session id

        self.additional_data.prompt = self.default_prompt # 控制台提示符,该额外数据是一个返回字符串的函数

        self._load_needed_plugins()
        
    def _load_needed_plugins(self):
        '''加载需要的插件
        '''
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/clear'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/exit'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/exploit'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/help'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/lrun'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/option_manager'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/search'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/sessions'))
        self.load_plugin(plugin_manager.plugins_map.get('core_plugins/connections'))
        self.on_loaded()

    @property
    def prompt(self)->str:
        return self.current_session.additional_data.prompt()

    def default_prompt(self)->str:
        """默认的控制台提示符

        Returns:
            str: 控制台提示符
        """
        return colour.colorize(config.app_name, ['bold', 'underline'])+' '+colour.colorize('>', 'bold')+' '

    @property
    def session_map(self)->Dict[str, SessionAdapter]:
        '''返回当前session map
        '''
        return self.__session_map.copy()
    

    @property
    def current_session(self)->SessionAdapter:
        '''返回当前使用的session对象，没有则返回本身
        '''
        return self.__session_map.get(self.__current_session_id, self)

    def add_session(self, session:SessionAdapter):
        '''添加一个session
        '''
        self.__session_map[session.session_id] = session

    def del_session(self, session_id:str)->bool:
        '''删除一个存活的session
        '''
        session = self.__session_map.get(session_id, None)
        if session is None:
            return False
        session.on_destroy_before()
        self.__session_map.pop(session_id)
        return True

    def set_current_session(self, session_id:str):
        """设置当前的session id

        Args:
            session_id (str): 当前session id
        """
        self.__current_session_id = session_id