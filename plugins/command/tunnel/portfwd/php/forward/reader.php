<?php
//global: $conn_id
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);
set_time_limit(0);

function run($vars){
    extract($vars);
    session_id($conn_id);
    $ret = array('code'=>1, 'msg'=>'');
    session_start();
    if(array_key_exists('readbuf', $_SESSION)){
        session_write_close();
        while($_SESSION['run']){
            session_start();
            $readbuf = $_SESSION['readbuf'];
            if($readbuf != ''){
                $ret['msg'] = base64_encode($readbuf);
                $_SESSION['readbuf'] = '';
                session_write_close();
                break;
            }
            session_write_close();
            usleep(100000);
        }
    }else{
        $ret ['code'] = -1;
        unset($_SESSION);
        session_destroy();
    }
    return json_encode($ret);
}