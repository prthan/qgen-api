from fastapi import APIRouter, Depends, Response, status

from api.config import APIConfiguration as config
from api.server import APIContext, APIServer
from api.logger.logger import Logger
from modules.qgen.model_interaction_factory import ModelInteractionFactory

from .data_models import GenerateREQ, GenerateRES

router=APIRouter()

@router.on_event("startup")
def startup():
  logger=Logger.from_config()
  logger.init()
  logger.info("starting app module: qgen")
  ctx=APIContext(request=None, response=None, logger=logger)

  for model_name in config.model["list"]:
    model_cfg=config.data["model"][model_name]
    model_cfg["model_name"]=model_name
    logger.info(f"loading model: {model_name}, path: {model_cfg['path']} to {model_cfg['device']['type']}:{model_cfg['device']['index']}")
    mi=ModelInteractionFactory.createInstance(model_cfg)
    if mi != None:
      mi.load(ctx)
    logger.info(f"model {model_name} loaded")

@router.on_event("shutdown")
def shutdown():
  logger=Logger.from_config()
  logger.init()
  logger.info("shutting down module: qgen")
  

@router.post("/{model_name}/generate")
def generate(model_name, req: GenerateREQ, res: Response, ctx: APIContext = Depends(APIContext)):
  ctx.logger.info("model: " + model_name)
  ctx.logger.info("generate: " + req.model_dump_json())
  model_cfg=config.data["model"][model_name]
  mi=ModelInteractionFactory.createInstance(model_cfg)
  if mi == None:
    res.status_code=status.HTTP_400_BAD_REQUEST
    return {"error": "INVALID-MODEL-INTERACTION"}
  req.model=model_name
  return mi.generate(ctx, req, res)
