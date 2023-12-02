import logging
import uvicorn
import uuid
import datetime
from fastapi import FastAPI, Request, Response, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.logger.logger import Logger
from .config import APIConfiguration, Config
from .auth.auth_validator import validate_request

class APIContext:
  def __init__(self, request: Request, response: Response, logger=None):
    self.request=request
    self.response=response
    self.logger=request.state.logger if request != None else logger
    self.config=APIConfiguration
    self.app=APIServer

class Server:
  def __init__(self):
    self.state=\
    {
      "resources": {}
    }
    self.apiapp = FastAPI()
    self.logConfig={
      "version": 1,
      "loggers": 
      {
        "uvicorn.error": {"level": getattr(logging, APIConfiguration.logger["level"].upper())},
      },
    }
    logging.config.dictConfig(self.logConfig)
  
  def fromConfig(self, configFile):
    self.config=Config(configFile)
    return self
  
  def setConfig(self, config):
    self.config=config
    return self
  
  def addRoutes(self, routes):
    self.apiapp.include_router(routes, prefix=APIConfiguration.context)
    return self

  def addResource(self, name, obj):
    self.state['resources'][name]=obj

  def removeResource(self, name):
    del self.state['resources'][name]

  def resources(self):
    return self.state['resources']

  def resource(self, name):
    return self.state['resources'][name]

  def run(self):
    uvicorn.run(self.apiapp, host=self.config.listener['address'], port=int(self.config.listener['port']), log_config=self.logConfig)
  

APIServer=Server()
APIServer.setConfig(APIConfiguration)

@APIServer.apiapp.on_event("startup")
async def apiServerStart():
    logger=Logger.from_config()
    logger.init()
    logger.info("starting app: "+APIServer.config.name)
    dumpRoutes(APIServer.apiapp.routes)
    logger.info("listener address: "+APIConfiguration.listener['address']+", port: "+APIConfiguration.listener['port']+", context: "+APIConfiguration.context)

@APIServer.apiapp.on_event("shutdown")
def apiServerStop():
    logger=Logger.from_config()
    logger.init()
    logger.info("stopping app: "+APIServer.config.name)
    Logger.shutdown()

@APIServer.apiapp.middleware("http")
async def apiServerDispatch(request: Request, call_next):
    cid=str(uuid.uuid4())
    logger=Logger.from_config({"cid": cid})
    logger.init()
    request.state.cid=cid
    request.state.logger=logger
    
    startTime=datetime.datetime.now()
    logger.info("<<--<< "+request.method+" "+request.url.path)

    val_msg=validate_request(request)

    if val_msg != "" :
      response=JSONResponse(content=jsonable_encoder({
        "code": "UN-AUTHORIZED",
        "message": val_msg
      }),
      status_code=status.HTTP_401_UNAUTHORIZED)
      logger.error("[Request Validator] "+val_msg)
      logger.info(">>-->> status: {0}, http-method: {1}, http-href: {2}, node: {3}, user-agent: {4}"
      .format(str(response.status_code), request.method, request.url.path, APIConfiguration.id, request.headers["user-agent"]))
      return response
    
    response = await call_next(request)
    response.headers["x-reqid"]=cid
    
    endTime=datetime.datetime.now()
    diff=(endTime-startTime)
    servTime=diff.seconds*1000+diff.microseconds / 1000
    servTimeRes="ms"
    if servTime  > 1000:
      servTime /= 1000
      servTimeRes="s"

    logger.info(">>-->> status: {0}, http-method: {1}, http-href: {2}, node: {3}, user-agent: {4}, serv time: {5}"
    .format(str(response.status_code), request.method, request.url.path, APIConfiguration.id, request.headers["user-agent"], str(servTime) + " " + servTimeRes))
    return response

def dumpRoutes(routes):
  logger=Logger.from_config()
  logger.init()
  for route in routes:
    for method in route.methods:
      logger.info("added route => {} # {}".format(route.path, method))
