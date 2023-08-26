PLUGIN_METADATA = {
    "id": "mcdm_client",
    "version": "1.0.0",
    "name": "McdReforged manager client",
    "description": "McdReforged manager client",
    "author": "notnotype",
    "link": "https://github.com/notnotype/mcd-manager",
    "dependencies": {
       "mcdreforged": ">=2.0.0-alpha.1"
    }
}

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import os
import shutil
import requests 
from time import sleep
from typing import Optional
from pathlib import Path
from loguru import logger
from mcdreforged.api.decorator import new_thread
from mcdreforged.info_reactor.info import Info
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.command import SimpleCommandBuilder, Integer, Text, GreedyText, CommandContext

client: requests.session
config: dict
current_server_config: dict
base_url: str
time_to_die: int

class APIError(RuntimeError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

def server_status(status: int) -> str:
    # data.status 会返回的值及其解释：-1（状态未知）；0（已停止）；1（正在停止）；2（正在启动）；3（正在运行）
    if status == -1:
        return "状态未知"
    elif status == 0:
        return "已停止"
    elif status == 1:
        return "正在停止"
    elif status == 2:
        return "正在启动"
    elif status == 3:
        return "正在运行"

def api_get(url, data: dict) -> dict:
    resp = client.get(url, params={ **data, "apikey": config["apiKey"]})
    resp.raise_for_status()
    json_data = resp.json()
    if json_data["status"] == 200:
        logger.debug("api_get: {}", json_data["data"])
        return json_data["data"]
    else:
        raise APIError(json_data)

def api_post(url, data: dict) -> dict:
    resp = client.get(url, query={ "apikey": config["apiKey"] }, data=data)
    resp.raise_for_status()
    json_data = resp.json()
    if json_data["status"] == 200:
        return json_data["data"]
    else:
        raise APIError(json_data)

def open_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/open", { "uuid": uuid, "remote_uuid": remote_uuid })
    return data

def stop_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/stop", { "uuid": uuid, "remote_uuid": remote_uuid })
    return data

def kill_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/kill", { "uuid": uuid, "remote_uuid": remote_uuid })
    return data

def restart_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/restart", { "uuid": uuid, "remote_uuid": remote_uuid })
    return data

def command_instance(uuid: str, remote_uuid: str, command: str):
    data = api_get(f"{base_url}/api/protected_instance/open", { "uuid": uuid, "remote_uuid": remote_uuid, command: command })
    return data
  
def get_instance(uuid: str, remote_uuid: str):
    # data.status 会返回的值及其解释：-1（状态未知）；0（已停止）；1（正在停止）；2（正在启动）；3（正在运行）
    data = api_get(f"{base_url}/api/instance", { "uuid": uuid, "remote_uuid": remote_uuid })
    return data

def get_server_config(name: str) -> object: 
    for server in config["servers"]:
        if server["name"] == name:
            return server
    else:
        raise RuntimeError(f"Can't find server config for server {name}")

# handle mcdr event

builder = SimpleCommandBuilder()

@builder.command("!!mcdm")
@builder.command("!!mcdm help")
def handle_help(source: CommandSource, context: CommandContext):
    source.reply("this is command help for: !!mcdm help")

@builder.command("!!mcdm list")
def handle_list(source: CommandSource, context: CommandContext):
    text = ""
    for server in config["servers"]:
        instance = get_instance(server["uuid"], server["remote_uuid"])
        text += f"{server['name']:.20} - {server_status(instance['status'])}\n"
    source.reply(text)
  
@builder.command("!!mcdm start <server>")
def handle_start(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["server"])
    open_instance(server_config["uuid"], server_config["remote_uuid"])

@builder.command("!!mcdm stop <server>")
def handle_stop(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["server"])
    stop_instance(server_config["uuid"], server_config["remote_uuid"])
  
@builder.command("!!mcdm restart <server>")
def handle_restart(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["server"])
    restart_instance(server_config["uuid"], server_config["remote_uuid"])
  
@builder.command("!!mcdm sync <server>")
def handle_sync(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["mirror"])
    source_world = Path("./server/survival/world")
    target_world = Path("./server/mirror/world")
    shutil.copytree(source_world, target_world, dirs_exist_ok=True)
    restart_instance(server_config["uuid"], server_config["mirror"])

@builder.command("!!mcdm generate <server> <seed>")
def handle_generate(source: CommandSource, context: CommandContext):
    ...

@new_thread("mcdrm_thread")
def mcdrem_thread(server: PluginServerInterface):  # ugly implements
    global time_to_die
    while True:
        if time_to_die >= 60:
            time_to_die -= 1
        elif time_to_die > 0 and time_to_die < 60:
            stop_instance(current_server_config["uuid"], current_server_config["remote_uuid"])
        else:
            pass
        sleep(1)

def registry_command(server: PluginServerInterface):
    """
        !!mcdm
        !!mcdm help
        !!mcdm list
        !!mcdm start <server>
        !!mcdm stop <server>
        !!mcdm restart <server>
        !!mcdm sync <server>
        !!mcdm generate <server>
    """

    # define your command nodes
    builder.arg('server', Text)
    builder.arg('seed', Text)

    # done, now register the commands to the server
    builder.register(server)

def on_player_joined(server: PluginServerInterface, player: str, info: Info):
    global time_to_die
    time_to_die = 0

def on_player_left(server: PluginServerInterface, player: str, info: Info):
    global time_to_die
    time_to_die = current_server_config["close_after"]

def on_load(server: PluginServerInterface, prev: Optional[PluginServerInterface]):
    global client, config, base_url, current_server_config, time_to_die

    # load configurations
    conf_path = Path(f"{server.get_data_folder()}/mcdrm.yml")
    if (not (conf_path.exists() and conf_path.is_file())):
        with open(conf_path, 'w', encoding='utf8') as f1:
            with server.open_bundled_file('mcdrm.yml') as f2:
                f1.write(f2.read().decode('utf8'))
        
        logger.exception(f"Config file {conf_path.absolute()} not found. A default one has been generated")
    with open(conf_path, "r", encoding="utf8") as f:
        config = yaml.load(f, Loader=Loader)
    client = requests.Session()
    base_url = config["base_url"]
    current_server_config = get_server_config(config["server_name"])
    time_to_die = current_server_config["close_after"]
    # load configurations
    registry_command(server)
    mcdrem_thread(server)