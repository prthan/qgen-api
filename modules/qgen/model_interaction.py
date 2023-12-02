from .data_models import GenerateREQ, GenerateRES

from fastapi import Response, status

class ModelInteraction:
  def __init__(self, model_cfg) -> None:
    self.model_cfg=model_cfg

  def load(self, ctx):
    pass

  def generate(self, ctx, req: GenerateREQ, res: Response)->GenerateRES: 
    pass