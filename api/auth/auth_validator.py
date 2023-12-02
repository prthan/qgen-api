import jwt
import base64
import json
from fastapi import Request

from api.config import APIConfiguration as config

def validate_request(request: Request):
  auth_cfg=config.data["auth"]

  if not "enabled" in  auth_cfg:
    return ""

  if auth_cfg["enabled"] == "false":
    return ""
  
  if auth_cfg["type"] == "jwt":
    if not "authorization" in request.headers:
      return "Missing Header"
    return validate_jwt(request, auth_cfg)
  
  if auth_cfg["type"] == "api-key":
    if not auth_cfg["api-key-header"] in request.headers:
      return "Missing Header"
    return validate_api_key(request, auth_cfg)

  if auth_cfg["type"] == "basic-auth":
    if not "authorization" in request.headers:
      return "Missing Header"
    return validate_basic_auth(request, auth_cfg)


def validate_jwt(request: Request, auth_cfg):
  pkstr=json.loads("\"" + base64.b64decode(auth_cfg["public-key"].encode("ascii")).decode('ascii') + "\"")
  pk=pkstr.encode("ascii")
  [_, token]=request.headers["authorization"].split()

  try:
    jwt.decode(token, pk, algorithms=[auth_cfg["signing-algo"]], audience="", issuer=auth_cfg["issuer"], options={
      "verify_signature=True": True,
      "verify_aud": False,
      "verify_iss": True,
      "verify_exp": True
    })
    return ""
  except Exception as ex:
    return str(ex)

def validate_api_key(request: Request, auth_cfg):
  api_key=request.headers[auth_cfg["api-key-header"]]
  if api_key != auth_cfg["api-key-value"]:
    return "Invalid API Key"
  return ""

def validate_basic_auth(request: Request, auth_cfg):
  [_, basic_auth]=request.headers["authorization"].split()
  basic_auth_val = base64.b64encode((auth_cfg["user"] + ":" + auth_cfg["pwd"]).encode("ascii")).decode('ascii')
  if basic_auth != basic_auth_val:
    return "Invalid Credentials"
  return ""
