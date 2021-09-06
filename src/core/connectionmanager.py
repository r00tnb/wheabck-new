from src.api.maintype.info import SessionOptions, SessionType, ServerInfo
import src.config as config
import sqlite3
from typing import Any, Dict, List, Union
import json, base64
import pickle

__all__ = ['Connection', 'connection_manager']

class Connection:
    '''描述webshell连接的属性，session需要通过该类来初始化
    '''

    def __init__(self) -> None:
        self.conn_id = -1
        self.options = SessionOptions()
        self.session_type = SessionType.PHP
        self.server_info = ServerInfo()

    @staticmethod
    def dumps(conn)->str:
        """将连接配置转为json字符串

        Args:
            conn ([type]): 连接对象

        Returns:
            str: json字符串
        """
        ret = {}
        ret['conn_id'] = conn.conn_id
        ret['options'] = {}
        for o in conn.options.options_map.values():
            ret['options'][o.name] = base64.b64encode(pickle.dumps(o.value)).decode()
        ret['session_type'] = conn.session_type.name
        ret['server_info'] =base64.b64encode( pickle.dumps(conn.server_info)).decode()
        return json.dumps(ret)
    
    @staticmethod
    def loads(data:str):
        """从json字符串中加载一个Connection对象

        Args:
            data (str): json字符串

        Returns:
            Connection: 生成的连接对象
        """
        data:dict = json.loads(data)
        ret = Connection()
        ret.conn_id = data['conn_id']
        for n, v in data['options'].items():
            v = base64.b64decode(v)
            v = pickle.loads(v)
            o = ret.options.get_option(n)
            if o is None:
                ret.options.add_option(n, v, '')
            else:
                o.set_value(v)
        ret.session_type = SessionType[data['session_type']]
        ret.server_info = pickle.loads(base64.b64decode(data['server_info']))
        return ret

class ConnectionManager:
    '''用于管理记录的webshell连接
    '''

    def __init__(self) -> None:
        self.conn = sqlite3.connect(config.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()

        self.json_table_name = 'json_data'
        self.conn_table_name = 'webshell_connections'

        # 初始化数据库
        self.cur.execute(f'CREATE TABLE IF NOT EXISTS {self.json_table_name}(\
            conn_id INTEGER,name TEXT, data TEXT)')
        self.cur.execute(f'CREATE TABLE IF NOT EXISTS {self.conn_table_name}(\
            conn_id INTEGER PRIMARY KEY, connection BLOB)') # connection字段为Connection对象的序列化值
        self.conn.commit()

    def get_json_data(self, conn_id:int, name:str)->Union[Union[dict,list], None]:
        '''获取指定的json数据
        '''
        self.cur.execute(f'select * from {self.json_table_name} where conn_id=? and name=?', (conn_id, name))
        row = self.cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row['data'])
        except:
            return None

    def add_json_data(self, conn_id:int, name:str, data:Union[dict,list])->bool:
        '''添加新的json数据
        '''
        try:
            self.cur.execute(f'insert into {self.json_table_name}(conn_id, name, data) values (?,?,?)', (
                conn_id, name, json.dumps(data)))
            self.conn.commit()
            return True
        except:
            return False
        
    def update_json_data(self, conn_id:int, name:str, data:Union[dict,list])->bool:
        '''更新指定的json数据
        '''
        try:
            self.cur.execute(f'update {self.json_table_name} set data=? where conn_id=? and name=?', (json.dumps(data),
                conn_id, name))
            self.conn.commit()
            return True
        except:
            return False

    def del_json_data(self, conn_id:int, name:str):
        '''删除指定的json数据
        '''
        self.cur.execute(f'delete from {self.json_table_name} where conn_id=? and name=?', (conn_id, name))
        self.conn.commit()

    def del_connection(self, conn_id:int):
        '''删除指定连接
        '''
        self.cur.execute(f'delete from {self.conn_table_name} where conn_id=?', (conn_id, ))
        self.conn.commit()

    def get_all_connections(self)->List[Connection]:
        '''获取所有保存的连接
        '''
        self.cur.execute(f'select * from {self.conn_table_name}')
        ret = []
        for row in self.cur.fetchall():
            try:
                conn:Connection = Connection.loads(row['connection'])
                conn.conn_id = row['conn_id'] # 防止两个id不一致
                ret.append(conn)
            except Exception as e:
                raise e
                continue
        return ret

    def get_connection(self, conn_id:int)->Union[Connection, None]:
        '''获取指定的连接
        '''
        self.cur.execute(f'select * from {self.conn_table_name} where conn_id=?', (conn_id,))
        row = self.cur.fetchone()
        if row is None:
            return None
        try:
            conn:Connection = Connection.loads(row['connection'])
            conn.conn_id = row['conn_id'] # 防止两个id不一致
            return conn
        except:
            return None

    def copy_connection(self, conn_id:int)->bool:
        """在表中复制一条连接信息

        Args:
            conn_id (int): 连接id

        Returns:
            bool: 成功返回True，否则False
        """
        try:
            self.cur.execute(f'insert into {self.conn_table_name}(connection) select connection from {self.conn_table_name} where conn_id=?',
                (conn_id,))
            self.conn.commit()
            return True
        except:
            return False

    def add_or_update_connection(self, connection:Connection)->int:
        """添加或更新连接信息, 当连接id存在时更新，否则新增

        Args:
            connection (Connection): 连接对象

        Returns:
            int: 操作成功返回添加或更新的连接id，失败返回-1
        """
        try:
            if self.get_connection(connection.conn_id) is None:# 添加
                value = Connection.dumps(connection)
                self.cur.execute(f'insert into {self.conn_table_name}(connection) values (?)', (value,))
                self.conn.commit()
                self.cur.execute(f'select conn_id from {self.conn_table_name} where connection=?', (value, ))
                row = self.cur.fetchone()
                if row is None:
                    return -1
                return row['conn_id']
            else:#更新
                self.cur.execute(f'update {self.conn_table_name} set connection=? where conn_id=?', 
                (Connection.dumps(connection), connection.conn_id))
                self.conn.commit()
                return connection.conn_id
        except Exception as e:
            raise e
            return -1


connection_manager = ConnectionManager()