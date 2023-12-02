import json
import uuid
import traceback
import datetime
import functools

from threading import Event
from concurrent.futures import ThreadPoolExecutor

import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
from fastapi import Response, status

from api.config import APIConfiguration as config
from modules.qgen.data_models import GenerateREQ, GenerateRES
from modules.utils import to_params, stop_watch, unique_values
from modules.qgen.model_interaction import ModelInteraction
from nemo.collections.nlp.models.token_classification.punctuation_capitalization_model import PunctuationCapitalizationModel

class Doc2QueryGenerator(ModelInteraction):
  def __init__(self, model_cfg) -> None:
    super().__init__(model_cfg)

  def load(self, ctx):
    model_name=self.model_cfg["model_name"]
    tokenizer = T5Tokenizer.from_pretrained(self.model_cfg["path"])
    ctx.app.addResource(model_name+".tokenizer", tokenizer)
    ctx.logger.info(f'[{model_name}] created tokenizer')

    kwargs={
      "torch_dtype": torch.float16,
      "device_map": "auto"
    }

    if self.model_cfg["device"] != None and self.model_cfg["device"]["index"] != None:
      kwargs["device_map"]=self.model_cfg["device"]["index"]

    generator = T5ForConditionalGeneration.from_pretrained(self.model_cfg["path"], **kwargs)
    ctx.app.addResource(model_name+".generator", generator)
    ctx.logger.info(f'[{model_name}] created generator')

    punct_capz_model = PunctuationCapitalizationModel.from_pretrained("punctuation_en_distilbert")      
    ctx.app.addResource(model_name+".punct_capz", punct_capz_model)
    ctx.logger.info(f'[{model_name}] created punctuation capitalization model')

  def generate(self, ctx, req: GenerateREQ, res: Response):
    model_name=req.model
    model_cfg=config.data["model"][model_name]
    params_cfg=model_cfg["params"]

    device="auto"
    if self.model_cfg["device"] != None and self.model_cfg["device"]["type"] != None:
      device=f'{self.model_cfg["device"]["type"]}:{self.model_cfg["device"]["index"]}'

    tokenizer=ctx.app.resource(model_name+".tokenizer") 
    generator=ctx.app.resource(model_name+".generator")
    punct_capz_model=ctx.app.resource(model_name+".punct_capz")

    if tokenizer==None:
      res.status_code=status.HTTP_400_BAD_REQUEST
      return {"error": "INVALID-MODEL-NAME"}
    
    contents=req.content
    content_list_tokens=[tokenizer(
      content,
      max_length=512,
      add_special_tokens=True,
      truncation=True,
      padding="max_length",
      pad_to_max_length=True,
      return_tensors="pt"
    ).input_ids.to(device) for content in contents]
    items=[{"content": "", "metrics": {"input_tokens": 0, "output_tokens":0, "total_time": ""}} for x in range(len(content_list_tokens))]

    ctx.logger.debug("contents: ")
    for i,x in enumerate(contents):
      ctx.logger.info(f'[{i}] [token length={len(content_list_tokens[i][0])}] {x}')  
      items[i]["metrics"]["input_tokens"]=len(content_list_tokens[i][0])

    params=to_params(model_name, req)
    ctx.logger.debug("params: " + json.dumps(params))

    for i,input_ids in enumerate(content_list_tokens):
      sw=stop_watch()
      sw.start("total_time")
      outputs = generator.generate(
        input_ids=input_ids, 
        do_sample=True, 
        **params
      )
      items[i]["metrics"]["total_time"]=sw.stop("total_time")
      items[i]["metrics"]["output_tokens"]=functools.reduce(lambda a,c:a+c, [len(x) for x in outputs])

      questions = [tokenizer.decode(ids, skip_special_tokens=True) for ids in outputs]
      similarity_threshold = req.similarity_threshold if req.similarity_threshold != None else model_cfg.get("similarity_threshold", 75)
      top_n = req.top_n if req.top_n != None else model_cfg.get("top_n", 10)
      unique_questions=unique_values(questions, params["top_k"], similarity_threshold)
      if len(unique_questions) > top_n:
        unique_questions = unique_questions[:top_n]

      items[i]["content"]=punct_capz_model.add_punctuation_capitalization(unique_questions)
    
    generated_content={"items": items}
    return generated_content

  
  