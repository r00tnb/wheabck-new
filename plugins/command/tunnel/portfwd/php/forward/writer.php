<?php
//global: $conn_id, $writebuf
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);

function run($vars){
    extract($vars);
    session_id($conn_id);
    $ret = 1;
    session_start();
    if(array_key_exists('writebuf', $_SESSION)){
        $_SESSION['writebuf'] .= $writebuf;
        session_write_close();
    }else{
        $ret = -1;
        unset($_SESSION);
        session_destroy();
    }
    return $ret;
}