<?php
//global: $pwd, $path

function run($vars){
    extract($vars);
    $ret = array('code'=>0, 'list'=>array());
    chdir($pwd);
    if(is_dir($path)){
        $l = scandir($path);
        if($l === false){
            $ret['code'] = -1;
        }else{
            foreach($l as $name){
                if($name == '.' || $name == '..') continue;
                $ret['list'][] = base64_encode($name);
            }
            $ret['code'] = 1;
        }
    }
    return json_encode($ret);
}