<?php
//global: $outpipe, $inpipe, $pwd
function run($vars){
    extract($vars);
    chdir($pwd);
    if(file_exists($outpipe))
        unlink($outpipe);
    if(file_exists($inpipe))
        unlink($inpipe);
}