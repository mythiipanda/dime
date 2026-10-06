from v2.main import app
from workspaces.routes import router as workspaces_router

app.include_router(workspaces_router, prefix="/api")
