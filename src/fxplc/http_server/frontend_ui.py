import functools
from typing import Any, List

from nicegui import ui
from nicegui.functions.refreshable import refreshable

from fxplc.client.FXPLCClient import RegisterDef, RegisterType
from fxplc.http_server.processor import perform_register_read, perform_register_write, resume_serial, \
    pause_serial, is_running, perform_register_write_bit
from fxplc.http_server.mytypes import VariableDefinition


def register_ui(variables: List[VariableDefinition]) -> None:
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
