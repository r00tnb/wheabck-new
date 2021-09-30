<?php
/**
 * 使用UDP服务器处理请求,针对客户端请求应该满足如下格式：
 * +-----+--------+--------+----------+
 * | cmd | sockid | length | data     |
 * +-----+--------+--------+----------+
 * | 1   | 1      | 2      | Variable |
 * +-----+--------+--------+----------+
 * cmd      指定当前动作类型, 可用值：1(connect客户端新建tcp连接), 2(read客户端读取数据), 3(write客户端写入数据), 4(close客户端关闭连接)
 * sockid   指定对应的socket编号，当cmd为2,3时指定要操作的socket, 1时指定新建连接的地址类型（值为4表示ipv4地址，6表示ipv6地址），4时值为0表示关闭UDP服务器（所以socket编号应该从1开始）
 * length   指定数据字段长度，单位字节,大端字节序。cmd为2，4时无意义将置为0
 * data     指定数据部分。当cmd为3时为传输的数据，为1时后俩字节为端口号，之前的为地址（结合sockid判断类型，ipv4 4字节， ipv6 16字节）, 为2，4时无意义将不发送该字段
 * 
 * UDP服务器向客户端请求的响应满足如下格式：
 * +------+--------+----------+
 * | code | length | data     |
 * +------+--------+----------+
 * | 1    | 2      | Variable |
 * +------+--------+----------+
 * code     指定操作是否成功，可用值：0（成功），1（一般性失败），2（连接超时），3（连接拒绝），4（不存在的sockid），7（不支持的cmd）
 * length   指定data字段的长度，大端字节序，单位字节
 * data     根据请求返回数据。
 * 
 * 对于远端的转发请求采用直接转发并存储在临时buf中
 */
//global: $host, $port
set_time_limit(0);
ignore_user_abort(0);
class Connection{
    const BUF_SIZE = 4096;//接收缓冲大小

    public $sock;//stream资源对象
    public $buf = '';
    public $type;
    public $remmote_addr = '';//与sock对应的远端地址，类似127.0.0.1:8080
    public $addr = '';//与UDP服务器交互远程地址类似 127.0.0.1:8080

    public function __construct($sock, $type, $raddr){
        $this->sock = $sock;
        $this->type = $type;
        $this->remote_addr = $raddr;
    }
    public function recvall_to_buf(){//从远端接收数据并存储在buf中
        if(strlen($this->buf)>Connection::BUF_SIZE) return;
        switch($this->type){
            case SOL_UDP:
                if(($buf=stream_socket_recvfrom($this->sock, Connection::BUF_SIZE, 0, $remmote_addraddr)) !== false ){
                    $this->buf .= $buf;
                }
                break;
            case SOL_TCP:
                if(($buf = fread($this->sock, Connection::BUF_SIZE)) !== false){
                    $this->buf .= $buf;
                }
                break;
        }
    }
    public function flush_buf($server){//将buf中的数据写入当前与之对应的客户端连接
        if($this->buf != '' && $this->addr != ''){
            $server->reply(0, $this->buf, $this->addr);
            $this->buf = '';
            $this->addr='';
        }
    }
    public function close($server){
        if($this->addr != ''){
            $server->reply(1, 'CLOSED', $this->addr);
        }
        fclose($this->sock);
    }
    public function sendall($data){//向远端写入数据
        switch($this->type){
            case SOL_UDP:
                return stream_socket_sendto($this->sock, $data, 0, $this->remmote_addr);
            case SOL_TCP:
                return fwrite($this->sock, $data);
        }
        return false;
    }
}
class UDPServer{
    const CONNECT = 1;
    const READ = 2;
    const WRITE = 3;
    const CLOSE = 4;

    public $ret = array('code'=>1, 'msg'=>'');
    private $addr;
    private $server;
    private $connection_list;// {'id':connection}
    public function __construct($addr){
        $this->addr = $addr;
    }
    
    public function init(){
        if(($this->server = stream_socket_server("udp://$this->addr", $errno, $errstr, STREAM_SERVER_BIND))===false){
            $this->ret['code'] = -1;
            if($errno === 0) $this->ret['code'] = -2;
            $this->ret['msg'] = base64_encode("$errno $errstr");
            return false;
        }
        $this->connection_list[0] = new Connection($this->server, SOL_UDP, '');
        return true;
    }

    public function reply($code, $data, $addr){
        $length = strlen($data);
        $buf = pack('Cn', $code, $length);
        stream_socket_sendto($this->server, $buf, 0, $addr);
        stream_socket_sendto($this->server, $data, 0, $addr);
    }

    public function generate_id(){//生成一个可用的socketid,失败返回false
        if(count($this->connection_list) > 255) return false;
        $id = mt_rand(1, 255);
        while(array_key_exists($id, $this->connection_list)){
            $id = mt_rand(1, 255);
        }
        return $id;
    }

    public function test($data){
        $this->ret['code'] = -1;
        $this->ret['msg'] = base64_encode("$data");
        return true;
    }

    public function handle($conn){//处理socket可读状态,返回true则结束UDPserver
        if($this->server === $conn->sock){
            if(($buf = stream_socket_recvfrom($this->server, 4, 0, $addr))===false) return false;
            $cmd = unpack('C', substr($buf, 0, 1))[1];
            $sockid = unpack('C', substr($buf, 1, 1))[1];
            $length = unpack('n', substr($buf, 2, 2))[1];
            switch($cmd){
                case UDPServer::CONNECT:
                    if(($buf = stream_socket_recvfrom($this->server, 6, 0, $addr))!==false){
                        $host = inet_ntop(substr($buf, 0, $length-2));
                        $port = unpack('n', substr($buf, $length-2, 2))[1];
                        if(($sock = stream_socket_client("tcp://[$host]:$port", $errno, $errstr, 3))!==false){
                            $id = $this->generate_id();
                            if($id !== false){
                                $this->connection_list[$id] = new Connection($sock, SOL_TCP, "$host:$port");
                                $this->reply(0, pack('C', $id), $addr);//成功返回sockid
                            }else{
                                $this->reply(1, 'The socket has reached its limit 255', $addr);
                            }
                        }else{
                            $this->reply(2, "$errno $errstr", $addr);
                        }
                    }else{
                        $this->reply(1, 'Recv data failed!', $addr);
                    }
                    break;
                case UDPServer::READ:
                    if(array_key_exists($sockid, $this->connection_list)){
                        $tmp = $this->connection_list[$sockid];
                        $tmp->addr = $addr;//先存地址，后续再将数据传回客户端
                    }else{
                        $this->reply(4, '', $addr);
                    }
                    break;
                case UDPServer::WRITE:
                    if(array_key_exists($sockid, $this->connection_list)){
                        if(($buf = stream_socket_recvfrom($this->server, $length, 0, $addr))!==false){
                            $tmp = $this->connection_list[$sockid];
                            $tmp->sendall($buf);
                            $this->reply(0, '', $addr);
                        }else{
                            $this->reply(1, 'Recv data failed!', $addr);
                        }
                    }else{
                        $this->reply(4, '', $addr);
                    }
                    break;
                case UDPServer::CLOSE:
                    if($sockid === 0){//全部关闭
                        $this->reply(0, '', $addr);
                        $this->close();
                        return true;// 结束
                    }else if(array_key_exists($sockid, $this->connection_list)){
                        $tmp = $this->connection_list[$sockid];
                        unset($this->connection_list[$sockid]);
                        $tmp->close($this);
                        $this->reply(0, '', $addr);
                    }else{
                        $this->reply(4, '', $addr);
                    }
                    break;
                default:
                    $this->reply(7, '', $addr);
            }
        }else{
            $conn->recvall_to_buf();
        }
        return false;
    }

    public function close(){
        foreach($this->connection_list as $id=>$c){//关闭socket
            if($id !== 0)
                $c->close($this);
        }
        fclose($this->server);
    }

    public function start(){
        $w = $e = array();
        while(true){
            $read = array();
            foreach($this->connection_list as $conn){
                $read[] = $conn->sock;
            }
            $r = stream_select($read, $w, $e, NULL);
            if($r){
                foreach($read as $sock){
                    foreach($this->connection_list as $conn){
                        if($conn->sock === $sock){
                            if($this->handle($conn)){
                                return;
                            }
                        }
                    }
                }
            }else{
                $this->ret['code'] = -3;
                $this->close();
                break;
            }
            // 处理待读取数据的客户端
            foreach($this->connection_list as $conn){
                $conn->flush_buf($this);
            }
        }
    }
}

function run($vars){
    extract($vars);
    $server = new UDPServer("$host:$port");
    if($server->init()){
        $server->start();
    }
    return json_encode($server->ret);
}