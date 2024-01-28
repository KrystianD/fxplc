import json
import os.path
from typing import Any, Optional, cast

import uvicorn
from fastapi import HTTPException, Body
from nicegui import app
from nicegui import ui
from starlette.responses import Response

from fxplc.client.number_type import NumberType
from fxplc.http_server.frontend_ui import register_ui
from fxplc.http_server.processor import perform_register_read, perform_register_write, resume_serial, \
    pause_serial, run_serial_task, perform_register_write_bit, perform_register_read_bit
from fxplc.http_server.mytypes import VariableDefinition, VariablesFile, RuntimeSettings
from fxplc.http_server.transport import TransportConfig
from fxplc.http_server.utils import read_yaml_file


class PrettyJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(content, indent=2, sort_keys=True).encode("utf-8")


def get_runtime_settings() -> RuntimeSettings:
    return cast(RuntimeSettings, app.state.runtime_settings)


@app.put("/pause", response_class=PrettyJSONResponse)  # type: ignore
async def pause_put():
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    pause_serial()
    return "OK"


@app.put("/resume", response_class=PrettyJSONResponse)  # type: ignore
async def resume_put():
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    resume_serial()
    return "OK"


@app.get("/raw/{register}", response_class=PrettyJSONResponse)  # type: ignore
async def raw_get(register: str) -> Any:
    return await perform_register_read(register, NumberType.WordSigned)


@app.put("/raw/{register}", response_class=PrettyJSONResponse)  # type: ignore
async def raw_put(register: str,
                  value: Optional[int | bool] = None,
                  value_body: Optional[int | bool] = Body(default=None)) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    if value is not None:
        value_to_set = value
    elif value_body is not None:
        value_to_set = value_body
    else:
        raise HTTPException(status_code=400, detail="no value")

    return await perform_register_write(register, value_to_set, NumberType.WordSigned)


@app.put("/raw/{register}/enable", response_class=PrettyJSONResponse)  # type: ignore
async def raw_enable_put(register: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    return await perform_register_write_bit(register, True)


@app.put("/raw/{register}/disable", response_class=PrettyJSONResponse)  # type: ignore
async def raw_disable_put(register: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    return await perform_register_write_bit(register, False)


@app.put("/raw/{register}/toggle", response_class=PrettyJSONResponse)  # type: ignore
async def raw_toggle_put(register: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    val = await perform_register_read_bit(register)
    return await perform_register_write_bit(register, not val)


def find_variable_def(name: str) -> VariableDefinition:
    var_defs = [x for x in get_runtime_settings().variables if x.name == name]
    if len(var_defs) == 0:
        raise HTTPException(status_code=404, detail="variable not found")
    var_def = var_defs[0]
    return var_def


@app.get("/variable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_get() -> Any:
    resp = []
    for var_def in get_runtime_settings().variables:
        val = await perform_register_read(var_def.register, var_def.number_type)
        resp.append({
            "name": var_def.name,
            "register": var_def.register,
            "value": val,
        })
    return resp


@app.get("/variable/{name}", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_get(name: str) -> Any:
    var_def = find_variable_def(name)

    val = await perform_register_read(var_def.register, var_def.number_type)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": val,
    }


@app.put("/variable/{name}", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_put(name: str,
                             value: Optional[int | bool] = None,
                             value_body: Optional[int | bool] = Body(default=None)) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    var_def = find_variable_def(name)

    if value is not None:
        value_to_set = value
    elif value_body is not None:
        value_to_set = value_body
    else:
        raise HTTPException(status_code=400, detail="no value")
    value_set = await perform_register_write(var_def.register, value_to_set, var_def.number_type)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/enable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_enable_put(name: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    var_def = find_variable_def(name)

    value_set = await perform_register_write_bit(var_def.register, True)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/disable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_disable_put(name: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    var_def = find_variable_def(name)

    value_set = await perform_register_write_bit(var_def.register, False)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/toggle", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_toggle_put(name: str) -> Any:
    if not get_runtime_settings().rest_enabled:
        raise HTTPException(status_code=400, detail="REST disabled")

    var_def = find_variable_def(name)

    val = await perform_register_read_bit(var_def.register)
    value_set = await perform_register_write_bit(var_def.register, not val)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


def run_server(args: Any) -> None:
    runtime_settings = RuntimeSettings()

    variables_path = args.variables

    if variables_path is not None:
        if not os.path.exists(variables_path):
            print("file specified by --variables option doesn't exist")
            exit(1)

        variables_data = read_yaml_file(variables_path)
        runtime_settings.variables = VariablesFile(**variables_data).variables

    app.state.runtime_settings = runtime_settings

    started = False

    transport_config = TransportConfig(path=args.path)

    def on_startup() -> None:
        nonlocal started
        if started:
            return
        started = True
        run_serial_task(transport_config)

    app.on_startup(on_startup)

    register_ui(runtime_settings)

    ui.run_with(app, mount_path=args.base_href, title="FXPLC server")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, access_log=False)
