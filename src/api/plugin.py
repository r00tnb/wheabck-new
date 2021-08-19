import abc
from src.api.ui.cmdline import Cmdline
from typing import List
from .session import SessionType, ServerInfo, Session

class Plugin(metaclass=abc.ABCMeta):
    '''所有插件应该实现该接口,插件指的是实现了Plugin的类

    插件类的类属性表示插件的属性，派生类需覆盖这些属性来配置当前插件
    '''

    name = 'plugin' # 插件名称,这可能用于显示，但不作为唯一性的判断，唯一性判断使用plugin_id
    author = 'r00tnb' # 插件作者
    plugin_id = '' # 该字段会在插件加载时自动填充
    description = 'This is a plugin for wheabck!' # 该插件的简要描述信息
    help_info = 'No help information!' # 该插件较详细的描述
    supported_session_types = list(SessionType) # 支持的session类型列表

    def __init__(self):
        self.session:Session

    @abc.abstractmethod
    def on_loading(self, session:Session)-> bool:
        """当尝试加载该插件实例时会调用该方法(这只在当前session在supported_session_types列表中时才会调用)

        Args:
            session (Session): 加载该插件的session实例

        Returns:
            bool: 若插件支持该session返回True不支持返回False
        """
        self.session = session
        return True

    def on_loaded(self):
        '''session加载完所有插件实例后会调用已加载插件的该方法
        '''
        pass

    def on_destroy(self):
        '''session销毁前，会调用所有已加载插件实例的该方法
        '''
        pass
