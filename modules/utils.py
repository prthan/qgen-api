import json
import datetime
from fuzzywuzzy import fuzz

from api.config import APIConfiguration as config

def diff(s, e):
  d=e-s
  t=d.seconds*1000+d.microseconds / 1000
  return f"{t} ms"

def to_params(model_name, req):
  model_cfg=config.data["model"][model_name]
  params_cfg=model_cfg["params"]
  params=dict(
    top_k=req.top_k if req.top_k != None else params_cfg.get("top_k", 10),
    max_length=req.top_n if req.top_n != None else params_cfg.get("max_length", 5),
    num_return_sequences=req.top_k if req.top_k != None else params_cfg.get("top_k", 10)
  )
  
  return params

def val(cfg, name, default_value=None):
  return cfg[name] if name in cfg else cfg.get(name, default_value)

def unique_values(values, top_k, similarity_threshold):
  unique_values = []
  for i in range(top_k-1,-1,-1):
    unique = True
    for j in range(0,i):
      if fuzz.ratio(values[i], values[j]) > similarity_threshold:
        unique = False
        break
    if unique:
      unique_values.append(values[i])
  return unique_values

class stop_watch:
  def __init__(self) -> None:
    self.timers={}

  def diff(self, s, e):
    d=e-s
    t=d.seconds*1000+d.microseconds / 1000
    return f"{t} ms"

  def start(self, name):
    self.timers[name]={"start": datetime.datetime.now()}

  def stop(self, name):
    self.timers[name]["stop"]=datetime.datetime.now()
    return self.get(name)
  
  def get(self, name):
    return self.diff(self.timers[name]["start"], self.timers[name]["stop"])
  
