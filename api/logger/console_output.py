import datetime
from dateutil import parser
import re

class ConsoleOutput:
  TEXT=\
  {
    "rich":\
    {
      "error": "\x1b[31m[Error]\x1b[0m",
      "info" : "\x1b[36m[ Info]\x1b[0m",
      "warn" : "\x1b[33m[ Warn]\x1b[0m",
      "debug": "\x1b[32m[Debug]\x1b[0m",
      "trace": "\x1b[32m[Trace]\x1b[0m"
    },
    "plain":\
    {
      "error": "[Error]",
      "info" : "[ Info]",
      "warn" : "[ Warn]",
      "debug": "[Debug]",
      "trace": "[Trace]"
    }
  }  
  
  def __init__(self, options):
    self.options={"mode": "rich", "format": "[#{ts}] #{level} #{msg}", "ts-format":"%Y/%m/%d %H:%M:%S", **options}

  def parse_logline_format(self, format):
    logLineParts=[]
    pattern="\#\{([^}]+)\}"
    start=0
    for match in re.finditer(pattern, format, re.MULTILINE):
      matchPos=match.span()
      logLineParts.append({"t": "t", "v": format[start:matchPos[0]]})
      logLineParts.append({"t": "v", "v": match.group(1)})
      start=matchPos[1]
    logLineParts.append({"t": "t", "v": format[start:]})
    return logLineParts

  def init(self):
    mode=self.options["mode"]
    format=self.options["format."+mode] if "format."+mode in self.options else self.options["format"]
    self.log_line_parts=self.parse_logline_format(format)

  def log(self, record):
    opts=self.options
    ts=parser.isoparse(record["ts"])
    ts=ts.replace(tzinfo=datetime.timezone.utc)
    ts=ts.astimezone()
    r={**record}
    r["ts"]=ts.strftime(opts["ts-format"])
    r["level"]=ConsoleOutput.TEXT[opts["mode"]][r["level"]]
    print("".join(map(lambda x: x["v"] if x["t"]=="t" else r[x["v"]] if x["v"] in r else "", self.log_line_parts)), *r["extra"])
