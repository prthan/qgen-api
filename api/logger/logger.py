from datetime import datetime
import time
from api.config import APIConfiguration as config
from .console_output import ConsoleOutput
from .stream_output import StreamOutput

LOG_LEVE_TAG=\
{
  "plain":\
  {
    "error": "[Error]",
    "info" : "[ Info]",
    "warning" : "[ Warn]",
    "warn" : "[ Warn]",
    "debug": "[Debug]"
  },
  "colored":\
  {
    "error": "\x1b[31m[Error]\x1b[0m",
    "info" : "\x1b[36m[ Info]\x1b[0m",
    "warning" : "\x1b[33m[ Warn]\x1b[0m",
    "warn" : "\x1b[33m[ Warn]\x1b[0m",
    "debug": "\x1b[32m[Debug]\x1b[0m",
  }
}

class Logger:
  LEVELS={"trace" : 1, "debug" : 2, "info"  : 3, "warn"  : 4, "error" : 5}
  OUTPUT_TYPE_CLASSES={"console": ConsoleOutput, "stream": StreamOutput}

  def from_config(with_ctx=None):
    cfg=config.data["logger"]
    if with_ctx!=None:
      cfg["ctx"]=with_ctx
    return Logger(cfg)
  
  def __init__(self, options):
    output_type_classes=Logger.OUTPUT_TYPE_CLASSES
    self.options={"level": "trace", "mode": "rich", "ts": False, "ctx": {}, **options}
    output_cfg=options["outputs"] if "outputs" in options else {"console": {}}
    self.outputs=list(map(lambda x: output_type_classes[x](output_cfg[x]), 
                     filter(lambda x: x in output_type_classes, list(output_cfg.keys()))))
    

  def init(self):
    for output in self.outputs:
      output.init()

  def shutdown():
    StreamOutput.shutdown()
    
  def log(self, type, *args):
    opts=self.options
    if Logger.LEVELS[opts["level"]]>Logger.LEVELS[type]:
      return
    
    args_list=list(args)
    record={
      "level": type, 
      "msg": args_list.pop(0), 
      "extra": args_list, 
      "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), 
      "epoch": time.time() * 1000,
      **opts["ctx"]
    }
    for output in self.outputs:
      output.log(record)

  def canLog(self, level):
    return Logger.LEVELS[self.options.level]<Logger.LEVELS[level]
  
  def error(self, *args):
    self.log("error", *args)
  
  def warn(self, *args):
    self.log("warn", *args)    

  def info(self, *args):
    self.log("info", *args)
  
  def debug(self, *args):
    self.log("debug", *args)    

  def trace(self, *args):
    self.log("trace", *args)