<?php
//global: $pwd, $path, $data

function run($vars){
    extract($vars);
    $ret = '0';
    chdir($pwd);
    $f = fopen($path, 'wb');
    $r = fwrite($f, $data);
    fclose($f);
    if($r != strlen($data)) 
        $ret = '-1';
    else
        $ret = '1';
    return $ret;
}