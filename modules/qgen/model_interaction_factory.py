from modules.qgen.impl.doc2query import Doc2QueryGenerator


class __ModelInteractionFactory:
  def __init__(self) -> None:
    self.classMap={}

  def addImpl(self, type, clazz):
    self.classMap[type]=clazz

  def createInstance(self, model_cfg):
    clazz=self.classMap[model_cfg["mode"]] if model_cfg["mode"] in self.classMap else None
    return clazz(model_cfg) if clazz != None else None

ModelInteractionFactory=__ModelInteractionFactory()
ModelInteractionFactory.addImpl("doc2query:generator", Doc2QueryGenerator)
