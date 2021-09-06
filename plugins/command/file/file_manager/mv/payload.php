<?php
//global: $pwd, $source, $dest, $f

function run($vars){
    extract($vars);
    chdir($pwd);
    if(!file_exists($source)){
        return "Souce file not exists!";
    }
    if(is_dir($dest)){
        $dest = $dest . DIRECTORY_SEPARATOR . basename($source);
    }
    if(file_exists($dest) && !$f){
        return "Dest file exists";
    }
    if(rename($source, $dest)){
        return "ok";
    }
    return error_get_last()['message'];
}