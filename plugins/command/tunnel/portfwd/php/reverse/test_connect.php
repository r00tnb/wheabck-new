<?php
// 测试远程连接是否已建立，如果建立则会返回
//global: $sessionid
ini_set("session.use_trans_sid" ,0);
ini_set("session.use_only_cookies" ,0);
ini_set("session.use_cookies" ,0);
set_time_limit(0);

function run($vars){
    extract($vars);
    $ret = -1;
    session_id($sessionid);
    while(true){
        session_start();
        if(isset($_SESSION['run'])){
            if($_SESSION['run'] === true){
                $ret = 1;
                break;
            }elseif($_SESSION['run'] === false){
                break;
            }
        }else{
            break;
        }
        session_write_close();
        usleep(100000);
    }
    return $ret;
}