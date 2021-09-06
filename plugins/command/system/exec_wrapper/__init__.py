from typing import Dict, Union
from api import Session, logger, tablor, utils, Command, CommandExecutor, Plugin, Cmdline, CommandReturnCode, CommandType
import argparse, sqlite3, os
import base64

def get_plugin_class():
    return ExecWrapperPlugin

class CommandWrapper:
    '''描述命令包装器信息
    '''
    def __init__(self, name:str, command_executor:CommandExecutor, description:str, code:bytes) -> None:
        self.name = name
        self.command_executor = command_executor
        self.code = code # Python代码
        self.description = description

    def exec(self, cmd:str, verbose=False)->Union[bytes, None]:
        """执行传入的命令

        Args:
            cmd (str): 命令字符串

        Returns:
            Union[bytes, None]: 返回命令执行结果，失败返回None
        """
        if self.code:
            a = {'cmd':cmd}
            exec(self.code, globals(), a)
            cmd = a.get('cmd')
            if verbose:
                logger.info(f"最终命令行：{cmd}")
            if self.command_executor:
                return self.command_executor.exec(cmd.encode())
        return None


class ExecWrapperPlugin(Plugin, Command, CommandExecutor):
    name = "命令包装器"
    description = "对命令执行进行包装，以便完成复杂操作"
    command_name = 'exec_wrapper'
    command_type = CommandType.SYSTEM_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        self.parse.add_argument('cmd', help="传入命令包装器的命令(使用-w选项指定包装器名称，否则使用默认的)", nargs='?')
        
        parse1 = self.parse.add_argument_group("设置")
        ex = parse1.add_mutually_exclusive_group()
        ex.add_argument('-a', '--add', help="添加一个命令包装器（进入询问模式来添加）", action='store_true')
        ex.add_argument('-e', '--edit', help="编辑指定的命令包装器")
        ex.add_argument('-r', '--remove', help="删除指定名称的命令包装器")
        ex.add_argument('-d', '--set-default', help="设置默认使用的命令包装器名称(默认是第一个创建的)")
        
        parse2 = self.parse.add_argument_group("状态")
        parse2.add_argument('-v', '--verbose', help="显示最终执行的命令行", action='store_true')
        parse2.add_argument('-s', '--show', help="显示当前已有的命令包装器", action='store_true')
        parse2.add_argument('-w', '--wrapper-name', help="指定要使用的命令包装器名称")

        self.help_info = self.parse.format_help()

        self.command_wrappers:Dict[str, CommandWrapper] = {} #保存当前的命令包装器
        self.default_wrapper_name:str = None # 默认使用的包装器名称 

    def on_loading(self, session: Session) -> bool:
        return super().on_loading(session)

    def exec(self, cmd: bytes) -> Union[bytes, None]:
        cw = self.command_wrappers.get(self.default_wrapper_name)
        if cw is None:
            return None
        return cw.exec(cmd.decode(errors='ignore'))

    def add(self)->CommandReturnCode:
        code = r'''# 编辑你的命令包装器代码
# 使用并更改全局变量cmd，来对命令进行包装甚至更改

cmd = cmd+' 2>&1'
        '''
        name = input("命令包装器名称： ")
        if name in self.command_wrappers:
            logger.error('存在相同名称的命令包装器！')
            return CommandReturnCode.FAIL
        command_executor_id = input("命令执行器ID（直接回车使用默认值）： ")
        ce:CommandExecutor = None
        if command_executor_id == '':
            command_executor_id = self.session.options.get_option('command_executor_id').value
        if command_executor_id == self.plugin_id:
            logger.error("命令执行器不能指定自身！！")
            return CommandReturnCode.FAIL
        for plugin in self.session.plugins_list:
            if isinstance(plugin, CommandExecutor) and plugin.plugin_id == command_executor_id:
                ce = plugin
        if ce is None:
            logger.error("指定的命令执行器不存在！")
            return CommandReturnCode.FAIL
        description = input("描述： ")
        code = utils.edit_on_editor(code.encode(), self.session.options.get_option('editor').value, f'命令包装器-{name}.py')
        if code is None:
            logger.error("编辑器打开失败！")
            return CommandReturnCode.FAIL
        
        self.command_wrappers[name] = CommandWrapper(name, ce, description, code)
        if self.default_wrapper_name is None:
            self.default_wrapper_name = name
        logger.info(f"命令包装器`{name}`添加成功!", True)
        return CommandReturnCode.SUCCESS

    def edit(self, name:str)->CommandReturnCode:
        cw = self.command_wrappers.get(name)
        if cw is None:
            logger.error(f"指定的命令包`{name}`装器不存在！")
            return CommandReturnCode.FAIL

        logger.info("直接回车不做更改！")
        name = input(f"命令包装器名称({cw.name})： ")
        if name == '':
            name = cw.name
        elif name in self.command_wrappers:
            logger.error('存在相同名称的命令包装器！')
            return CommandReturnCode.FAIL
        command_executor_id = input(f"命令执行器ID（{cw.command_executor.plugin_id}）： ")
        if command_executor_id == self.plugin_id:
            logger.error("命令执行器不能指定自身！！")
            return CommandReturnCode.FAIL
        ce:CommandExecutor = None
        if command_executor_id != '':
            for plugin in self.session.plugins_list:
                if isinstance(plugin, CommandExecutor) and plugin.plugin_id == command_executor_id:
                    ce = plugin
        else:
            ce = cw.command_executor
            command_executor_id = ce.plugin_id
        if ce is None:
            logger.error("指定的命令执行器不存在！")
            return CommandReturnCode.FAIL
        description = input(f"描述({cw.description})： ")
        code = utils.edit_on_editor(cw.code, self.session.options.get_option('editor').value, f'命令包装器-{name}.py')
        if code is None:
            logger.error("编辑器打开失败！")
            return CommandReturnCode.FAIL

        self.command_wrappers[name] = CommandWrapper(name, ce, description, code)
        if self.default_wrapper_name == cw.name:
            self.default_wrapper_name = name
        self.command_wrappers.pop(cw.name)
        logger.info(f"命令包装器`{name}`编辑完毕!", True)
        return CommandReturnCode.SUCCESS

    def show(self):
        table = [['名称', '命令执行器', '描述']]
        i, a = 0, 0
        for cw in self.command_wrappers.values():
            table.append([cw.name, cw.command_executor.plugin_id, cw.description])
            i += 1
            if self.default_wrapper_name == cw.name:
                a = i

        print(tablor(table, title="存在的命令包装器", border=False, pos=a, pos_str='[*]'))

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if args.add:
            return self.add()
        elif args.edit is not None:
            return self.edit(args.edit)
        elif args.remove is not None:
            if args.remove in self.command_wrappers:
                self.command_wrappers.pop(args.remove)
                logger.info(f"已删除命令包装器`{args.remove}`!", False)
            else:
                logger.error(f"命令包装器`{args.remove}`不存在!")
                return CommandReturnCode.FAIL
        elif args.set_default is not None:
            if args.set_default in self.command_wrappers:
                self.default_wrapper_name = args.set_default
                logger.info(f"默认命令包装器 => {args.set_default}")
            else:
                logger.error(f"指定了不存在的命令包装器`{args.set_default}`！")
                return CommandReturnCode.FAIL
        elif args.show:
            self.show()
        elif args.cmd is not None:
            name = args.wrapper_name if args.wrapper_name is not None else self.default_wrapper_name
            cw = self.command_wrappers.get(name)
            if cw is None:
                logger.error("指定的命令包装器不存在！")
                return CommandReturnCode.FAIL
            data = cw.exec(args.cmd, args.verbose)
            if data is None:
                logger.error("命令执行失败！")
                return CommandReturnCode.FAIL
            print(data.decode(self.session.options.get_option('encoding').value, errors='ignore'))
        else:
            print(self.help_info)
            return CommandReturnCode.FAIL

        return CommandReturnCode.SUCCESS

    def on_destroy(self):
        config = {'default':self.default_wrapper_name, 'wrappers':{}}
        for cw in self.command_wrappers.values():
            config['wrappers'][cw.name] = [cw.command_executor.plugin_id, cw.description, base64.b64encode(cw.code).decode()]
        self.session.save_json('exec_wrapper-config', config)

    def on_loaded(self):
        data = self.session.load_json('exec_wrapper-config')
        if data is None:
            return
        self.default_wrapper_name = data.get('default')
        for name, v in data.get('wrappers', {}).items():
            for plugin in self.session.plugins_list:
                if isinstance(plugin, CommandExecutor) and plugin.plugin_id == v[0]:
                    self.command_wrappers[name]=CommandWrapper(name, plugin, v[1], base64.b64decode(v[2].encode()))

        if self.default_wrapper_name not in self.command_wrappers:
            self.default_wrapper_name = None