from v2.main import app
from warehouse_tables import router as warehouse_router
from workspaces.routes import router as workspaces_router

app.include_router(warehouse_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
