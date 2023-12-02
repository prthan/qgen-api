from typing import Union, List
from pydantic import BaseModel

class Metrics(BaseModel):
  input_tokens: Union[int, None]=None
  output_tokens: Union[int, None]=None
  total_time: Union[str, None]=None

class GenerateREQ(BaseModel):
  model: Union[str, None]=None
  content: Union[List[str], None]=None
  top_k: Union[int, None]=None
  top_n: Union[int, None]=None
  similarity_threshold: Union[int, None]=None
  max_length: Union[int, None]=None

class GenerateRES(BaseModel):
  items: Union[List[str], None]=None
  metrics: Metrics


