from typing import Dict, List
from api import Session, logger, utils, tablor, colour, Plugin, Command, CommandReturnCode, CommandType, Cmdline
from .rules import Rule, ForwardRule, ReverseRule
import argparse
import re
import curses

def get_plugin_class():
    return PortFwdPlugin

class PortFwdPlugin(Plugin, Command):
    name = "端口转发"
    description = '可进行正向反向的端口转发'
    command_name = 'portfwd'
    command_type = CommandType.POST_COMMAND

    def __init__(self):
        self.parse = argparse.ArgumentParser(prog=self.command_name, description=self.description)
        parses = self.parse.add_subparsers()
        add_parser = parses.add_parser("add", help="添加一个端口转发规则.")
        config_group = add_parser.add_argument_group("配置选项")
        o = config_group.add_mutually_exclusive_group()
        o.add_argument('-R', help="开启该选项则进行反向端口转发（远程流量转发到本地）", action='store_true')
        o.add_argument('-L', help="开启该选项则进行正向端口转发（本地流量转发到远程）（默认）", action='store_true', default=True)
        config_group.add_argument('-l', '--lhost', help="本地ip地址", default='127.0.0.1')
        config_group.add_argument('-p', '--lport', help="本地端口", type=int, required=True)
        config_group.add_argument('-r', '--rhost', help="远程ip地址", default="127.0.0.1")
        config_group.add_argument('-P', '--rport', help="远程端口", type=int, required=True)
        config_group.add_argument('-s', '--uploadsize', help="每次上传的数据包大小。能够使用单位b（字节）、k（千字节）、m（兆字节）默认b.例如1024, 1024b, 1024k等。若设置为0（默认），则数据将在一次请求中上传", 
            type=self._getsize, default="0")
        config_group.add_argument('-t', '--timeout', help="规则的空闲超时时间（单位秒）,默认180秒", type=float, default=180.)
        config_group.add_argument('-u', '--udp', help="是否转发udp流量，默认是转发tcp流量", action='store_true')
        add_parser.set_defaults(func=self._add)

        show_parser = parses.add_parser("show", help="显示当前使用的转发规则.")
        show_parser.set_defaults(func=self._show)
        flush_parser = parses.add_parser("flush", help="指定规则ID用于刷新该转发连接, 刷新会停止规则下的所有连接并重新启动.")
        flush_parser.add_argument('rule_id', help="规则ID")
        flush_parser.set_defaults(func=self._flush)
        delete_parser = parses.add_parser("delete", help="停止并删除指定ID的规则.")
        delete_parser.add_argument('rule_id', help="规则ID", nargs='+')
        delete_parser.set_defaults(func=self._delete)
        
        self.help_info = self.parse.format_help()
        self.forward_map:Dict[str, Rule] = {}

    def on_loading(self, session: Session) -> bool:
        session.register_complete_func(self.docomplete)
        return super().on_loading(session)

    def _getsize(self, size: str)-> int:
        '''用于转换传入的--uploadsize参数
        '''
        size = size.strip().rstrip('bB').lower()
        try:
            util = size[-1]
            if util not in 'km':
                return int(size)

            size = float(size[:-1])
            if util == 'k':
                size *= 1024
            elif util == 'm':
                size *= 1024*1024
            return int(size)
        except Exception as e:
            logger.error(f"上传数据包大小参数`{size}`格式错误!")
            raise e

    def _get_humen_size(self, size:int)->str:
        """获取人类友好的数据大小,仅用于显示

        Args:
            size (int): 字节数

        Returns:
            str: 人类友好的数据大小显示
        """
        if size < 1024:
            return str(size)
        elif size < 1024*1024:
            return '%.2fKB'%(size/1024)
        else:
            return '%.2fMB'%(size/1024/1024)

    def run(self, cmdline: Cmdline) -> CommandReturnCode:
        args = self.parse.parse_args(cmdline.options)
        if hasattr(args, 'func'):
            return args.func(args)
        self.parse.error("未提供子命令！")
        return CommandReturnCode.FAIL

    def _show(self, args:argparse.Namespace)->CommandReturnCode:
        table = [['ID', '转发规则', '上传分片大小', '存活的连接数量', '状态']]
        for ID, rule in self.forward_map.items():
            tmp = []
            tmp.append(ID)
            tmp.append(rule.rule_name)
            tmp.append(f"{'不分片' if rule.upload_buf_size == 0 else self._get_humen_size(rule.upload_buf_size)}")
            tmp.append(rule.connections_count)
            state = colour.colorize('停止', 'bold', 'red')
            if rule.is_alive():
                state = colour.colorize('运行', 'bold', 'green')
            tmp.append(state)
            table.append(tmp)
        print(tablor(table, border=False, title="转发规则列表", aligning="right-3"))
        return CommandReturnCode.SUCCESS

    def _delete(self, args:argparse.Namespace)->CommandReturnCode:
        id_list = args.rule_id
        if not id_list:
            return CommandReturnCode.SUCCESS
        ret = CommandReturnCode.FAIL
        logger.info("正在删除指定的规则...")
        for ID in id_list:
            for i, rule in self.forward_map.items():
                if i.startswith(ID):# 前缀匹配规则ID
                    rule.close()
                    self.forward_map.pop(i)
                    logger.info(f"已删除规则 `{rule.rule_name}`", False)
                    ret = CommandReturnCode.SUCCESS
                    break
        if ret == CommandReturnCode.FAIL:
            logger.error("指定规则都不存在！")
        return ret

    def _add(self, args:argparse.Namespace)-> CommandReturnCode:
        rule = None
        if args.R:# reverse
            rule = ReverseRule(self.session, args.lhost, args.lport, args.rhost, args.rport, args.uploadsize, args.udp, args.timeout)
        elif args.L: # forward
            rule = ForwardRule(self.session, args.lhost, args.lport, args.rhost, args.rport, args.uploadsize, args.udp, args.timeout)
        else:
            logger.error("添加规则发生未知错误！")
            return CommandReturnCode.FAIL
        self.forward_map[rule.rule_id] = rule
        rule.start()
        logger.info(f"规则`{rule.rule_name}`已添加并启动成功！")
        return CommandReturnCode.SUCCESS

    def _flush(self, args:argparse.Namespace)-> CommandReturnCode:
        '''更新端口转发
        '''
        for ID, rule in self.forward_map.items():
            if ID.startswith(args.rule_id):# 前缀匹配ID
                rule.flush()
                logger.info(f"规则`{rule.rule_name}`刷新成功！")
                return CommandReturnCode.SUCCESS

        logger.error(f"指定的规则`{args.rule_id}`不存在！")
        return CommandReturnCode.FAIL

    def docomplete(self, text: str)-> List[str]:
        result = []
        match = re.fullmatch(r'(%s +)(\w*)'%self.command_name, text)
        if match:
            for key in ['flush', 'delete', 'add', 'show']:
                if key.startswith(match.group(2).lower()):
                    result.append(match.group(1)+key+' ')
        return result

    def on_destroy(self):
        self._delete(argparse.Namespace(rule_id=list(self.forward_map.keys())))