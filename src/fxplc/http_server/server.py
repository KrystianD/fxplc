import functools
import json
import os.path
from typing import Any, List, Optional

import uvicorn
from fastapi import HTTPException, Body
from nicegui import app
from nicegui import ui
from nicegui.functions.refreshable import refreshable
from pydantic.dataclasses import dataclass
from starlette.responses import Response

from fxplc.client.FXPLCClient import RegisterDef, RegisterType
from fxplc.http_server.processor import perform_register_read, perform_register_write, resume_serial, \
    pause_serial, run_serial_task, is_running, perform_register_write_bit, perform_register_read_bit
from fxplc.http_server.utils import read_yaml_file


@dataclass
class VariableDefinition:
    name: str
    register: str


@dataclass
class VariablesFile:
    variables: List[VariableDefinition]


variables: List[VariableDefinition] = []


class PrettyJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(content, indent=2, sort_keys=True).encode("utf-8")


@app.put("/pause", response_class=PrettyJSONResponse)  # type: ignore
async def pause_put():
    pause_serial()
    return "OK"


@app.put("/resume", response_class=PrettyJSONResponse)  # type: ignore
async def resume_put():
    resume_serial()
    return "OK"


@app.get("/raw/{register}", response_class=PrettyJSONResponse)  # type: ignore
async def raw_get(register: str) -> Any:
    return await perform_register_read(register)


@app.put("/raw/{register}", response_class=PrettyJSONResponse)  # type: ignore
async def raw_put(register: str,
                  value: Optional[int | bool] = None,
                  value_body: Optional[int | bool] = Body(default=None)) -> Any:
    if value is not None:
        value_to_set = value
    elif value_body is not None:
        value_to_set = value_body
    else:
        raise HTTPException(status_code=400, detail="no value")

    return await perform_register_write(register, value_to_set)


@app.put("/raw/{register}/enable", response_class=PrettyJSONResponse)  # type: ignore
async def raw_enable_put(register: str) -> Any:
    return await perform_register_write_bit(register, True)


@app.put("/raw/{register}/disable", response_class=PrettyJSONResponse)  # type: ignore
async def raw_disable_put(register: str) -> Any:
    return await perform_register_write_bit(register, False)


@app.put("/raw/{register}/toggle", response_class=PrettyJSONResponse)  # type: ignore
async def raw_toggle_put(register: str) -> Any:
    val = await perform_register_read_bit(register)
    return await perform_register_write_bit(register, not val)


def find_variable_def(name: str) -> VariableDefinition:
    var_defs = [x for x in variables if x.name == name]
    if len(var_defs) == 0:
        raise HTTPException(status_code=404, detail="variable not found")
    var_def = var_defs[0]
    return var_def


@app.get("/variable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_get() -> Any:
    resp = []
    for var_def in variables:
        val = await perform_register_read(var_def.register)
        resp.append({
            "name": var_def.name,
            "register": var_def.register,
            "value": val,
        })
    return resp


@app.get("/variable/{name}", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_get(name: str) -> Any:
    var_def = find_variable_def(name)

    val = await perform_register_read(var_def.register)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": val,
    }


@app.put("/variable/{name}", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_put(name: str,
                             value: Optional[int | bool] = None,
                             value_body: Optional[int | bool] = Body(default=None)) -> Any:
    var_def = find_variable_def(name)

    if value is not None:
        value_to_set = value
    elif value_body is not None:
        value_to_set = value_body
    else:
        raise HTTPException(status_code=400, detail="no value")
    value_set = await perform_register_write(var_def.register, value_to_set)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/enable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_enable_put(name: str) -> Any:
    var_def = find_variable_def(name)

    value_set = await perform_register_write_bit(var_def.register, True)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/disable", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_disable_put(name: str) -> Any:
    var_def = find_variable_def(name)

    value_set = await perform_register_write_bit(var_def.register, False)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


@app.put("/variable/{name}/toggle", response_class=PrettyJSONResponse)  # type: ignore
async def variables_name_toggle_put(name: str) -> Any:
    var_def = find_variable_def(name)

    val = await perform_register_read_bit(var_def.register)
    value_set = await perform_register_write_bit(var_def.register, not val)

    return {
        "name": var_def.name,
        "register": var_def.register,
        "value": value_set,
    }


def run_server(args: Any) -> None:
    global variables

    variables_path = args.variables

    if variables_path is not None:
        if not os.path.exists(variables_path):
            print("file specified by --variables option doesn't exist")
            exit(1)

        variables_data = read_yaml_file(variables_path)
        variables = VariablesFile(**variables_data).variables

    def on_startup() -> None:
        run_serial_task(args)

    app.on_startup(on_startup)

    @ui.page('/')  # type: ignore
    async def ui_index() -> None:
        def ch(e: Any) -> None:
            set_running = e.value

            if set_running:
                resume_serial()
            else:
                pause_serial()

        notification_timeout = 1000

        @refreshable  # type: ignore
        async def ui_vars() -> None:
            def_to_val = {}
            try:
                for var_def in variables:
                    val = await perform_register_read(var_def.register)
                    def_to_val[var_def.name] = val
            except:
                ui.notify(f"Unable to update fetch data", type="negative", timeout=notification_timeout)
                return

            for var_def in variables:
                val = def_to_val[var_def.name]

                reg = RegisterDef.parse(var_def.register)

                if reg.type in (RegisterType.Input,):
                    u = ui.switch(text=var_def.name, value=bool(val))
                    u.disable()
                if reg.type in (RegisterType.Output,):
                    u = ui.switch(text=var_def.name, value=bool(val))
                    u.disable()
                if reg.type in (RegisterType.Memory,):
                    async def fn1(var_def_: VariableDefinition, e: Any) -> None:
                        was_enabled = e.value
                        action_str = "enabled" if was_enabled else "disabled"
                        try:
                            await perform_register_write_bit(var_def_.register, was_enabled)
                            ui.notify(f"{var_def_.name} {action_str}", type="positive", timeout=notification_timeout)
                        except:
                            ui.notify(f"Unable to update {var_def_.name} status", type="negative",
                                      timeout=notification_timeout)

                    with ui.row():
                        ui.switch(text=var_def.name, value=bool(val), on_change=functools.partial(fn1, var_def))
                if reg.type in (RegisterType.Data,):
                    async def fn2(ui_value_el_: Any, var_def_: VariableDefinition) -> None:
                        try:
                            await perform_register_write(var_def_.register, ui_value_el_.value)
                            ui.notify(f"{var_def_.name} set to {ui_value_el_.value}", type="positive",
                                      timeout=notification_timeout)
                        except:
                            ui.notify(f"Unable to update {var_def_.name} value", type="negative",
                                      timeout=notification_timeout)

                    with ui.row() as r:
                        r.style("align-items: center;")
                        ui_value_el = ui.number(label=var_def.name, value=int(val), on_change=None) \
                            .style("width: 300px")
                        ui.button(text="Set", on_click=functools.partial(fn2, ui_value_el, var_def))

        with ui.row():
            ui.switch(text="Running",
                      value=is_running(),
                      on_change=ch).props("color=red")
            ui.button(text="Refresh variables", on_click=ui_vars.refresh)
        ui.separator()

        await ui_vars()
        ui.separator()

    ui.run_with(app, mount_path=args.base_href, title="FXPLC server")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, access_log=False)
