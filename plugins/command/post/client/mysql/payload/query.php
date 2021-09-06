<?php
//global: $host, $user, $password, $database, $port, $sql

function run($vars){
    extract($vars);
    $ret = array('code'=>-2, 'msg'=>'', 'affected'=>0, 'result'=>array());
    if(function_exists('mysqli_connect')){
        $conn = @mysqli_connect($host, $user, $password, $database, $port);
        if(!$conn){
            $ret['code'] = -1;
            $ret['msg'] = 'Connect failed: '.mysqli_connect_error();
            $ret['msg'] = base64_encode($ret['msg']);
        }else{
            $r = @mysqli_query($conn, $sql);
            if($r === true){
                $ret['code'] = 2;
                $ret['affected'] = mysqli_affected_rows($conn);
            }elseif($r === false){
                $ret['code'] = 0;
                $ret['msg'] = 'Query failed: '.mysqli_error($conn);
                $ret['msg'] = base64_encode($ret['msg']);
            }else{
                $columns = array();
                if($fields = mysqli_fetch_fields($r)){
                    foreach($fields as $field){
                        $columns[] = base64_encode($field->name);
                    }
                    $ret['result'][] = $columns;
                }
                while($row=mysqli_fetch_assoc($r)){
                    $tmp = array();
                    foreach($row as $key=>$val){
                        $tmp[] = base64_encode($val);
                    }
                    $ret['result'][] = $tmp;
                }
                $ret['code'] = 1;
                mysqli_free_result($r);
            }
            @mysqli_kill($conn, mysqli_thread_id($conn));
            @mysqli_close($conn);
        }
    }
    return json_encode($ret);
}