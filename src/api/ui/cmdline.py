from typing import List, Union
import re

class Cmdline:
    '''用于解析或构造命令行字符串

    :param line: 命令行字符串或者字符串列表（第一项表示命令，后续为其参数）
    '''
    def __init__(self, line:Union[str, List[str]]):
        self.__cmdline:str = None # 命令行字符串
        self.__cmdlist:List[str] = [] # 解析后的命令加命令参数的列表
        if isinstance(line, str):
            self.__cmdline = line
            self.__cmdlist = list(self.__parsecmd(line))
        elif isinstance(line, list) or isinstance(line, tuple):
            self.__cmdlist = list(line)
            if len(self.__cmdlist) > 0 and self.__cmdlist[0] == '':
                self.__cmdlist = []
            if len(self.__cmdlist) == 0:
                self.__cmdline = ''
        else:
            raise ValueError('The type of Cmdline\'s options must be list,tuple or str!')

        if not self.__cmdlist:
            raise ValueError('Command line parsing error')
        

    @property
    def length(self)->int:
        '''命令行字符串的参数个数加1（即包括命令本身）
        '''
        return len(self.__cmdlist)
    
    @property
    def cmdline(self)->str:
        '''返回命令行字符串
        '''
        if self.__cmdline is None:
            if self.cmd is None:
                return ''
            else:
                tmp = list(self.__cmdlist)
                for i in range(len(tmp)):
                    if re.search(r'\s+', tmp[i]):
                        t = tmp[i].replace('"', '\"')
                        tmp[i] = f'"{t}"'
                self.__cmdline = ' '.join(tmp)

        return self.__cmdline

    @property
    def cmd(self)->str:
        '''获取命令名称
        '''
        return self.__cmdlist[0]
    
    @property
    def options(self)->List[str]:
        '''获取参数列表
        '''
        return self.__cmdlist[1:]

    def __parsecmd(self, line: str)-> List[str]:
        """将命令行字符串解析为参数列表形式，支持的引号包括' " `

        如："ls -l a" 转为["ls", "-l", "a"]

        Args:
            line (str): 命令行字符串

        Returns:
            List[str]: 解析完成的参数列表（第一项为命令名称），失败返回空列表
        """
        result = []
        # 解析命令字符串，转为命令列表的形式，如："ls -l a" 转为["ls", "-l", "a"]
        quote = None # 当前期待的引号
        quotestr = '"`\''
        end = 0
        space = ' \t\r\n'
        line = line.strip(space) # 命令行的开始与结束都不会有空白符
        length = len(line)
        for q in quotestr:
            if line.startswith(q):
                return []
        
        cur = ''
        quote_str= ''
        is_quote_over = False # 判断最后是否是从引号中退出
        while end < length:
            if line[end] in quotestr:
                if quote == line[end] and line[end-1] != '\\':
                    cur += quote_str.replace(f"\\{quote}", quote)
                    quote_str = ''
                    end += 1
                    quote = None
                elif quote is None:
                    quote = line[end]
                    end += 1
                else:
                    quote_str += line[end]
                    end += 1
                is_quote_over = True
                continue

            if quote is not None:
                quote_str += line[end]
                end += 1
                continue

            if line[end] not in space:
                cur += line[end]
                end += 1
                is_quote_over = False
                continue

            result.append(cur)
            cur = ''
            while line[end] in space:
                end += 1
            is_quote_over = False
        if quote is not None:
            return []
        if cur or is_quote_over:
            result.append(cur)
        return result