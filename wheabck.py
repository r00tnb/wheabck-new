#!/bin/python3
from posixpath import join
from typing import Dict
from src.console import terminal
from src.api import colour, CodeExecutor, tablor
from src.core.pluginmanager import plugin_manager
import argparse


def list_ce():
    table = [['代码执行器ID', '支持类型', '描述']]
    for plugin_class in plugin_manager.plugins_map.values():
        if issubclass(plugin_class, CodeExecutor):
            s = [t.name for t in plugin_class.supported_session_types]
            table.append([plugin_class.plugin_id, ', '.join(s), plugin_class.description])

    print(tablor(table, border=False))

def option_help(ceid:str):
    ce = plugin_manager.get_code_executor(ceid)
    if ce is None:
        print(colour.colorize(f'指定的代码执行器`{ceid}`不存在！'))
    table = [['选项名', '默认值', '描述 ']]
    for name, o in ce.options.items():
        table.append([name, o[0], o[1]])

    print(tablor(table, border=False, title=f"代码执行器`{ceid}`的选项"))

def generate(options:Dict[str, str], ceid:str):
    ce = plugin_manager.get_code_executor(ceid)
    if ce is None:
        print(colour.colorize(f'指定的代码执行器`{ceid}`不存在！'))
    
    ret = ce.generate(options)
    print(ret.decode())

if __name__ == '__main__':
    parse = argparse.ArgumentParser(prog="wheabck", description="webshell管理工具，要体验完整功能请进入交互模式")
    master_parse = parse.add_argument_group("主要")
    master_parse.add_argument('code_executor_id', help="指定一个要使用的代码执行器ID", nargs='?')
    master_parse.add_argument('-i', '--interactive', help="进入交互模式", action='store_true')
    master_parse.add_argument('-l', '--list', help="列出当前可用的代码执行器", action='store_true')
    
    option_parse = parse.add_argument_group("参数选项")
    option_parse.add_argument('-o', '--options', help="向代码执行器传递的参数", nargs='+')
    option_parse.add_argument('-t', '--type', help="生成的脚本内那类型, 默认PHP")
    option_parse.add_argument('-g', '--generate', help="生成webshell脚本", action='store_true')
    option_parse.add_argument('-O', '--options-help', help="显示代码执行器的额外参数帮助信息", action='store_true')

    args = parse.parse_args()
    ceid = args.code_executor_id
    if ceid is None:
        if args.list:
            list_ce()
        elif args.interactive:
            terminal.cmdloop()
        else:
            terminal.cmdloop()
    else:
        options = {'TYPE':'PHP'}
        if args.options:
            for o in args.options:
                o = o.strip()
                i = o.find('=')
                name = o[:i]
                value = o[i+1:]
                options[name] = value
        if args.type:
            options['TYPE'] = args.type
            
        if args.generate:
            generate(options, ceid)
        elif args.options_help:
            option_help(ceid)
        else:
            print(parse.format_help())
