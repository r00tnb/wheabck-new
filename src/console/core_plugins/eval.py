from typing import Any, Dict, List, Type, Union
from api import Plugin, Command, Cmdline, CommandReturnCode, CommandType, Session, logger, Payload
import argparse
from api.maintype.info import SessionType
from src.core.sessionadapter import SessionAdapter
from src.console.sessionmanager import ManagerSession
from src.core.connectionmanager import Connection
import src.config as config
import re, os

def get_plugin_class():
    return EvalPlugin

class EvalPlugin(Plugin, Command):
    name = 'eval'
    description = '执行Payload代码并获取结果'
    command_name = 'eval'
    command_type = CommandType.SYSTEM_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('payload', help="字符串形式的payload", nargs='?')
        self.parse.add_argument('-f', '--file', help="要执行的payload文件路径")
        self.parse.add_argument('-v', '--vars', help="要传递给payload的变量, 如`-v test = 123 id = 123`", nargs='+')
        self.help_info = self.parse.format_help()

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.file is not None:
            return self.eval_file(args.file, args.vars if args.vars is not None else [])
        elif args.payload is not None:
            return self.eval_payload(args.payload, args.vars if args.vars is not None else [])
        else:
            print(self.help_info)
        return CommandReturnCode.FAIL

    def eval_file(self, path:str, vars:List[str])->CommandReturnCode:
        payload = b''
        try:
            with open(path, 'rb') as f:
                payload = f.read()
        except:
            logger.error(f'payload文件`{path}`不存在！')
            return CommandReturnCode.FAIL
        return self.eval_payload(payload, vars)

    def eval_payload(self, payload:str, vars:List[str])->CommandReturnCode:
        if self.session.session_type == SessionType.PHP:
            payload = r'''
            function run($vars){
                extract($vars);
                chdir('%s');
                ob_start();
                %s
                $result = ob_get_contents();
                ob_end_clean();
                return $result;
            }
            '''%(self.session.server_info.pwd, payload)
        ret = self.session.eval(Payload.create_payload(payload.encode(), self.analysis_vars(vars), self.session.session_type))
        if ret is not None:
            print(ret.decode(self.session.options.get_option('encoding').value))
            return CommandReturnCode.SUCCESS
        else:
            logger.error("执行失败！")
        return CommandReturnCode.FAIL

    def analysis_vars(self, vars:List[str])->Dict[str, Any]:
        ret = {}
        for var in vars:
            i = var.find('=')
            if i == -1:
                continue
            name, value = var[:i], var[i+1:].strip('"`\'')
            ret[name] = value
        return ret