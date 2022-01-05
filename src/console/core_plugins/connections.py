from typing import List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, tablor, logger
import argparse, re
from src.core.sessionadapter import SessionAdapter
from src.console.sessionmanager import ManagerSession
from src.core.connectionmanager import Connection, connection_manager
import src.config as config
import re

def get_plugin_class():
    return ConnectionPlugin

class ConnectionPlugin(Plugin, Command):
    name = 'connections'
    description = '管理已保存的webshell连接'
    command_name = 'connections'
    command_type = CommandType.CORE_COMMAND

    manager_session:ManagerSession # 存储管理者session

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('-s', '--save-sessionid', help="保存指定的session到webshell连接，若不指定session id则保存当前session", nargs='?', const=True)
        self.parse.add_argument('-d', '--delete-connectionid', help="删除指定的连接，若不指定则尝试删除所有已保存的连接", nargs='*', type=int)
        self.parse.add_argument('-c', '--create-from-connectionid', help="从指定的连接创建一个session", type=int)
        self.parse.add_argument('-l', '--list', help="列出当前已保存的webshell连接", action='store_true')
        self.parse.add_argument('-r', '--replica', help="复制一个指定的连接")
        self.parse.add_argument('-e', '--edit', help="编辑一个指定的连接，会把指定连接的配置载入", type=int)
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        if isinstance(session, ManagerSession): # 保存管理者session实例
            ConnectionPlugin.manager_session = session
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.save_sessionid is not None:
            ID = args.save_sessionid
            if ID is True:
                if isinstance(self.session, ManagerSession):#保存当前编辑的连接配置
                    if not self.session.config.options.get_option('code_executor_id').value:
                        logger.error(f"当前连接配置未指定代码执行器ID！")
                        return CommandReturnCode.FAIL
                    if connection_manager.add_or_update_connection(self.session.config)!=-1:
                        logger.info(f"当前连接配置保存成功！", True)
                    else:
                        logger.error(f"当前连接配置保存失败！")
                        return CommandReturnCode.FAIL
                    return CommandReturnCode.SUCCESS
                ID = self.session.session_id
            return self.save_session(ID)
        elif args.delete_connectionid is not None:
            return self.delete_connections(args.delete_connectionid)
        elif args.create_from_connectionid is not None:
            return self.create_from_connection(args.create_from_connectionid)
        elif args.replica:
            return self.replica(args.replica)
        elif args.edit:
            return self.edit_connection(args.edit)
        elif args.list:
            self.list_connections()
        else:
            self.list_connections()
        return CommandReturnCode.SUCCESS

    def edit_connection(self, conn_id:int)->CommandReturnCode:
        """编辑连接配置

        Args:
            conn_id (int): 连接ID

        Returns:
            CommandReturnCode: 命令返回码
        """
        conn = connection_manager.get_connection(conn_id)
        if conn is None:
            logger.error("指定的连接不存在！")
            return CommandReturnCode.FAIL
        self.manager_session.config = conn
        self.manager_session.set_current_session(None)
        return self.manager_session.call_command(Cmdline(['set','code_executor_id',conn.options.get_option('code_executor_id').value]))

    def replica(self, conn_id:str)->CommandReturnCode:
        """创建一个指定连接的复制

        Args:
            conn_id (str): 连接ID

        Returns:
            CommandReturnCode: 命令返回码
        """
        if connection_manager.copy_connection(conn_id):
            logger.info('连接已被复制！')
            return CommandReturnCode.SUCCESS
        logger.error(f'连接`{conn_id}`复制失败！')
        return CommandReturnCode.FAIL

    def save_session(self, session_id:str)->CommandReturnCode:
        """保存指定的session

        Args:
            session_id (str): session id

        Returns:
            CommandReturnCode: 命令返回码
        """
        s:SessionAdapter = None
        for ID, session in self.manager_session.session_map.items():
            if ID.startswith(session_id):
                s = session
                break
        if s is not None:
            conn_id = connection_manager.add_or_update_connection(s.config)
            if conn_id!=-1:
                s.config.conn_id = conn_id
                logger.info(f"保存session`{session_id}`到连接成功！", True)
                return CommandReturnCode.SUCCESS
            else:
                logger.error(f"保存session`{session_id}`失败！")
        else:
            logger.error(f"session`{session_id}`不存在！")
        return CommandReturnCode.FAIL

    def delete_connections(self, ids:List[int])->CommandReturnCode:
        """删除指定的连接

        Args:
            ids (List[int]): 连接id列表

        Returns:
            CommandReturnCode: 命令返回码
        """
        delall = False
        if not ids and input("确定删除所有已保存的webshell连接吗？(y/n) ").lower() == 'y':
            delall = True
        ok_ids = []
        for conn in connection_manager.get_all_connections():
            if conn.conn_id in ids or delall:
                connection_manager.del_connection(conn.conn_id)
                logger.info(f"删除连接`{conn.conn_id}`成功")
                ok_ids.append(conn.conn_id)
        tmp = [str(ID) for ID in ids if ID not in ok_ids]
        if tmp and not delall:
            logger.warning(f"连接`{','.join(tmp)}`失败！")
            return CommandReturnCode.PARTIAL_SUCCESS
        return CommandReturnCode.SUCCESS
    
    def on_destroy(self):
        '''session销毁前保存当前session
        '''
        if isinstance(self.session, ManagerSession):
            return
        self.save_session(self.session.session_id)

    def create_from_connection(self, conn_id:int)->CommandReturnCode:
        """从连接中创建并切换到一个session

        Args:
            conn_id (int): 连接id

        Returns:
            CommandReturnCode: 命令返回码
        """
        conn = connection_manager.get_connection(conn_id)
        if conn is None:
            logger.error(f"连接`{conn_id}`不存在！")
            return CommandReturnCode.FAIL
        self.manager_session.config.conn_id = conn.conn_id
        self.manager_session.call_command(Cmdline(['set', 'code_executor_id', conn.options.get_option('code_executor_id').value]))
        for o in conn.options.options_map.values():
            self.manager_session.call_command(Cmdline(['set', o.name, str(o.value)]))
        return self.manager_session.call_command(Cmdline(['exploit']))

    
    def list_connections(self):
        """列出保存的连接
        """
        table = [['连接ID', '类型', '目标']]
        for conn in connection_manager.get_all_connections():
            table.append([conn.conn_id, conn.session_type.name, conn.options.get_option('target').value])
        print(tablor(table, border=False, title="连接列表"))
