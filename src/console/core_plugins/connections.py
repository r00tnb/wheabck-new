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
    description = 'Manage stored webshell connections'

    manager_session:ManagerSession # 存储管理者session

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.name, description=self.description)
        self.parse.add_argument('-s', '--save-sessionid', help="Specify the session ID to be saved. If not specified, the current session will be saved", nargs='?', const=True)
        self.parse.add_argument('-d', '--delete-connectionid', help="Delete the specified stored connection, or delete all if not specified", nargs='+', type=int)
        self.parse.add_argument('-c', '--create-from-connectionid', help="Creates a session from the specified connection", type=int)
        self.parse.add_argument('-l', '--list', help="List all saved connections", action='store_true')
        self.parse.add_argument('-r', '--replica', help="Specify a connection ID to create a replica")
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
                if isinstance(self.session, ManagerSession):
                    logger.error("You are not in a session. You must specify the session ID")
                    return CommandReturnCode.FAIL
                ID = self.session.session_id
            return self.save_session(ID)
        elif args.delete_connectionid is not None:
            return self.delete_connections(args.delete_connectionid)
        elif args.create_from_connectionid is not None:
            return self.create_from_connection(args.create_from_connectionid)
        elif args.replica:
            return self.replica(args.replica)
        elif args.list:
            self.list_connections()
        else:
            self.list_connections()
        return CommandReturnCode.SUCCESS

    def replica(self, conn_id:str)->CommandReturnCode:
        """创建一个指定连接的复制

        Args:
            conn_id (str): 连接ID

        Returns:
            CommandReturnCode: 命令返回码
        """
        if connection_manager.copy_connection(conn_id):
            logger.info('A connection was copied')
            return CommandReturnCode.SUCCESS
        logger.error(f'`{conn_id}`` connection copy failed')
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
            if connection_manager.add_or_update_connection(s.config):
                logger.info(f"Save session `{session_id}` to connection successfully", True)
                return CommandReturnCode.SUCCESS
            else:
                logger.error(f"Failed to save session `{session_id}` to connection")
        else:
            logger.error(f"Session `{session_id}` does not exist")
        return CommandReturnCode.FAIL

    def delete_connections(self, ids:List[int])->CommandReturnCode:
        """删除指定的连接

        Args:
            ids (List[int]): 连接id列表

        Returns:
            CommandReturnCode: 命令返回码
        """
        ok_ids = []
        for conn in connection_manager.get_all_connections():
            if conn.conn_id in ids:
                connection_manager.del_connection(conn.conn_id)
                logger.info(f"Deleted connection `{conn.conn_id}` successfully")
                ok_ids.append(conn.conn_id)
        tmp = [str(ID) for ID in ids if ID not in ok_ids]
        if tmp:
            logger.warning(f"Connections `{','.join(tmp)}` not exists")
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
            logger.error(f"Connection `{conn_id}` not exists")
            return CommandReturnCode.FAIL
        s = SessionAdapter(conn)
        logger.info(f"Session `{s.session_id}` created")
        if s.init_session():
            self.manager_session.add_session(s)
            self.manager_session.set_current_session(s.session_id)
            logger.info(f"Switch to session `{s.session_id}`")
            return CommandReturnCode.SUCCESS
        return CommandReturnCode.FAIL

    
    def list_connections(self):
        """列出保存的连接
        """
        table = [['Conn ID', 'Type', 'Target']]
        for conn in connection_manager.get_all_connections():
            table.append([conn.conn_id, conn.session_type.name, conn.options.get_option('target')])
        print(tablor(table, border=False, title="Connections Table"))


    @property
    def command_name(self) -> str:
        return self.name

    @property
    def command_type(self) -> CommandType:
        return CommandType.CORE_COMMAND