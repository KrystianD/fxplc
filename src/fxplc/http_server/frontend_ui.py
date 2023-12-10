import functools
from typing import Any

from nicegui import ui
from nicegui.functions.refreshable import refreshable

from fxplc.client.FXPLCClient import RegisterDef, RegisterType
from fxplc.http_server.mytypes import VariableDefinition, RuntimeSettings
from fxplc.http_server.processor import perform_register_read, perform_register_write, resume_serial, \
    pause_serial, is_running, perform_register_write_bit


def set_running(running: bool) -> None:
    if running:
        resume_serial()
    else:
        pause_serial()


def set_rest_enabled(runtime_settings: RuntimeSettings, enabled: bool) -> None:
    runtime_settings.rest_enabled = enabled


def register_ui(runtime_settings: RuntimeSettings) -> None:
    @ui.page('/')  # type: ignore
    async def ui_index() -> None:
        notification_timeout = 1000
        only_placeholder = True

        @refreshable  # type: ignore
        async def ui_vars() -> None:
            nonlocal only_placeholder
            if only_placeholder:
                only_placeholder = False
                return

            spinner_el = ui.spinner(size='lg')

            def_to_val = {}
            try:
                for var_def in runtime_settings.variables:
                    val = await perform_register_read(var_def.register)
                    def_to_val[var_def.name] = val
            except:
                ui.notify(f"Unable to update fetch data", type="negative", timeout=notification_timeout)
                return
            finally:
                spinner_el.delete()

            def emit_control(var_def: VariableDefinition) -> None:
                val = def_to_val[var_def.name]

                reg = RegisterDef.parse(var_def.register)

                if reg.type in (RegisterType.Input,):
                    u = ui.switch(text=var_def.name, value=bool(val))
                    u.disable()
                if reg.type in (RegisterType.Output, RegisterType.Memory,):
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

            groups = list(dict.fromkeys([x.group for x in runtime_settings.variables]))

            with ui.row():
                for group in groups:
                    with ui.card():
                        ui.label(text=group).style("font-size: 18px; font-weight: bold")
                        for var_def in (x for x in runtime_settings.variables if x.group == group):
                            emit_control(var_def)

        with ui.row():
            ui.switch(text="Running",
                      value=is_running(),
                      on_change=lambda x: set_running(x.value)).props("color=red")
            ui.button(text="Refresh variables", on_click=ui_vars.refresh)
            ui.switch(text="REST enabled",
                      value=runtime_settings.rest_enabled,
                      on_change=lambda x: set_rest_enabled(runtime_settings, x.value)).props("color=green")

        await ui_vars()
        ui_vars.refresh()
