from api.server import APIServer
from modules.qgen import routes as api_routes

APIServer \
  .addRoutes(api_routes.router) \
  .run()
