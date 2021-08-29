<?php
//global: $pwd, $path, $mode

function run($vars){
    extract($vars);
    chdir($pwd);
    umask(0);
    if(mkdir($path, $mode) === false) 
        return '-1';
    else
        return '1';
}