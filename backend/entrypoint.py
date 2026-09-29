from shared.config import runtime_v2_mode

if runtime_v2_mode() == "on":
    from v2.main import app
else:
    from app.main import app
