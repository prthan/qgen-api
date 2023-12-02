import redis.asyncio as redis
from datetime import datetime
import time
import json
import asyncio
import threading
import queue

class StreamOutput:
  STREAM_CLIENTS={}
  DISPATCHER_THREAD=None
  DISPATCHER_QUEUE=queue.Queue()
  RUN=threading.Event()

  def dispatcher_runner():
    asyncio.run(StreamOutput.dispatcher())

  async def dispatcher():
    while StreamOutput.RUN.is_set():
      log_line=StreamOutput.DISPATCHER_QUEUE.get()
      client=StreamOutput.STREAM_CLIENTS[log_line["name"]]
      await client.xadd(log_line["name"], log_line, id="*")
  
  def shutdown():
    StreamOutput.RUN.clear()

  def __init__(self, options):
    self.options={"extra": {}, **options}

  def init(self):
    if self.options["name"] in StreamOutput.STREAM_CLIENTS:
      return
    client=redis.Redis(host=self.options["host"], port=self.options["port"], password=self.options["password"], db=0, decode_responses=True)
    StreamOutput.STREAM_CLIENTS[self.options["name"]]=client
    self.client=client

    if StreamOutput.DISPATCHER_THREAD==None:
      print("starting dispatcher thread")
      StreamOutput.RUN.set()
      StreamOutput.DISPATCHER_THREAD=threading.Thread(target=StreamOutput.dispatcher_runner, name="logger-streamoutput-thread")
      StreamOutput.DISPATCHER_THREAD.start()

  def log(self, record):
    opts=self.options
    r={**record}
    log_line={"record": json.dumps({**r, **opts["extra"]}), "name": self.options["name"]}
    StreamOutput.DISPATCHER_QUEUE.put(log_line)
