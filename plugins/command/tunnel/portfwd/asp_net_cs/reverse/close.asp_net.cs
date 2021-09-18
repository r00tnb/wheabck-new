using System;
using System.Web;
using System.IO;
using System.Text;
using System.Runtime.Serialization;
using System.Threading;

public class Payload{
    public string Run(){
        string outfile = Path.Combine(Path.GetTempPath(), Global.sessionid+"_out");
        string infile = Path.Combine(Path.GetTempPath(), Global.sessionid+"_in");
        string signfile = Path.Combine(Path.GetTempPath(), Global.sessionid+"_sign");
        Mutex mut = new Mutex(false, Global.sessionid+"_test123");
        mut.WaitOne();
        if(File.Exists(outfile)){
            File.Delete(outfile);
        }
        if(File.Exists(infile)){
            File.Delete(infile);
        }
        if(File.Exists(signfile)){
            File.Delete(signfile);
        }
        mut.ReleaseMutex();
        return "";
    }
}