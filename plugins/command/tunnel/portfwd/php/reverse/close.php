<?php
//global: $sessionid
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);

function run($vars){
    extract($vars);
    session_id($sessionid);
    session_start();
    if(array_key_exists('run', $_SESSION)){
        $_SESSION['run'] = false;
        session_write_close();
    }else{
        unset($_SESSION);
        session_destroy();
    }
}