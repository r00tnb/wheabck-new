<?php
//global: $inpipe, $pwd, $cmd

function run($vars){
    extract($vars);
    chdir($pwd);
    if(file_exists($inpipe)){
        $in = @fopen($inpipe, 'wb');
        fwrite($in, $cmd);
        fclose($in);
    }else{
        return "-1";
    }
    return "1";
}