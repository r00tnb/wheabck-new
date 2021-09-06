from typing import List
from api import Cmdline, Session, Command, CommandReturnCode, Plugin, tablor, CommandType, logger
from src.console.sessionmanager import ManagerSession
import argparse

def get_plugin_class():
    return SessionManage

class SessionManage(Plugin, Command):
    name = 'sessions'
    description = "Manage session"
    command_name = 'sessions'
    command_type = CommandType.CORE_COMMAND

    manager_session:ManagerSession # 记录当前session管理的实例

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('-i', '--interact', help="Switch to the specified session with session id")
        self.parse.add_argument('-k', '--kill', help="Delete the specified session with session id(If not specified, all sessions will be deleted)", nargs='*')
        self.parse.add_argument('-l', '--list', help="List all active sessions", action='store_true')
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        if isinstance(session, ManagerSession):
            SessionManage.manager_session = session
        else:
            session.register_command(BgCommand(self.manager_session))
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.interact is not None:
            return self.switch_session(args.interact)
        elif args.kill is not None:
            ids = args.kill
            return self.kill_session(ids)
        elif args.list:
            self.list_session()
        else:
            self.list_session()
        return CommandReturnCode.SUCCESS

    def switch_session(self, session_id:str)->CommandReturnCode:
        """切换到指定的session

        Args:
            session_id (str): session id

        Returns:
            CommandReturnCode: 命令返回码
        """
        for ID in self.manager_session.session_map.keys():
            if ID.startswith(session_id):
                self.manager_session.set_current_session(ID)
                logger.info(f"Switch to session `{ID}`")
                return CommandReturnCode.SUCCESS
        logger.error(f"No session with id `{session_id}`")
        return CommandReturnCode.FAIL

    def kill_session(self, ids:List[str])->CommandReturnCode:
        """删除指定的session

        Args:
            ids (List[str]): session id列表

        Returns:
            CommandReturnCode: 命令返回码
        """
        if not ids:
            ids = list(self.manager_session.session_map.keys())
        err_ids = []
        for i in range(len(ids)):
            ok = False
            for ID in self.manager_session.session_map.keys():
                if ID.startswith(ids[i]):
                    ids[i] = ID
                    ok = True
                    break
            if not ok:
                err_ids.append(ids[i])
        if err_ids:
            logger.error(f"The specified session does not exist with ids `{','.join(err_ids)}`")
            return CommandReturnCode.FAIL
        for ID in ids:
            self.manager_session.del_session(ID)
            logger.info(f"Deleted session with id `{ID}`", False)
        return CommandReturnCode.SUCCESS

    def list_session(self):
        """列出所有活跃的session
        """
        table = [['Session ID', 'Type', 'Target']]
        active_id = 1
        for ID, session in self.manager_session.session_map.items():
            if session is not self.manager_session.current_session:
                active_id += 1
            table.append([session.session_id, session, session.options.get_option('target').value])

        print(tablor(table, border=False, pos=active_id))

    def on_destroy(self):
        '''程序退出后自动销毁所有session
        '''
        if isinstance(self.session, ManagerSession):
            self.kill_session(list(self.manager_session.session_map.keys()))


class BgCommand(Command):

    description = 'Switch the session to the background'
    command_name = 'bg'
    command_type = CommandType.CORE_COMMAND

    def __init__(self, session:ManagerSession) -> None:
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.help_info = self.parse.format_help()
        self.session = session

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        s = self.session.current_session
        self.session.set_current_session(None)
        logger.info(f"Background session `{s.session_id}`")
        return CommandReturnCode.SUCCESS