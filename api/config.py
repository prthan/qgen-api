import json
import re
import os

class Config:
  def __init__(self, configFileName):
    self.loadFromFile(configFileName)

  def loadFromFile(self, configFileName):
    print('loading config from file: '+configFileName)
    self.data=self.fileToJson(configFileName)
    for key in self.data:
      if key!="@include":
        setattr(self,key,self.data[key])
    if "@include" in self.data:
      for ikey in self.data['@include']:
        jobj=self.fileToJson(self.data['@include'][ikey])
        setattr(self, ikey, jobj)
        self.data[ikey]=jobj
        
  def fileToJson(self, file):
    f=open(file, "r")
    content=f.read()
    f.close()
    jobj=json.loads(self.updateVariables(content))
    return jobj

  def updateVariables(self, content):
    pattern="\$\{([^}]+)\}"
    updatedContent=""
    start=0
    for match in re.finditer(pattern, content, re.MULTILINE):
      matchPos=match.span()
      matchId=match.group(1).split(".")
      updatedContent += content[start:matchPos[0]]
      if matchId[0].upper()=='ENV':
        envValue=os.environ.get(matchId[1], "")
        if matchId[1]=="APP_HOME" and envValue=="": envValue="."
        updatedContent += envValue
      start=matchPos[1]
    updatedContent += content[start:]
    
    return updatedContent

APP_HOME=os.environ.get('APP_HOME', ".")
APP_ENV=os.environ.get("APP_ENV", "")
APP_CONFIG=os.environ.get("APP_CONFIG", APP_HOME + "/config") + ("/qgen-api.json" if APP_ENV=="" else "/qgen-api-"+APP_ENV+".json")

APIConfiguration=Config(APP_CONFIG)