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
import os
import requests 
from time import sleep
from pathlib import Path
from loguru import logger
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.command import SimpleCommandBuilder, Integer, Text, GreedyText, CommandContext

client: requests.session
config: object
base_url: str

class APIError(RuntimeError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

def server_status(status: int) -> str:
    # data.status 会返回的值及其解释：-1（状态未知）；0（已停止）；1（正在停止）；2（正在启动）；3（正在运行）
    match status:
        case -1: return "状态未知"
        case 0: return "已停止"
        case 1: return "正在停止"
        case 2: return "正在启动"
        case 3: return "正在运行"

def api_get(url, data: object) -> object:
    resp = client.get(url, params=data)
    resp.raise_for_status()
    json_data = resp.json()
    if json_data["status"] == 200:
        return json_data["data"]
    else:
        raise APIError(json_data)

def api_post(url, data: object) -> object:
    resp = client.get(url, data=data)
    resp.raise_for_status()
    json_data = resp.json()
    if json_data["status"] == 200:
        return json_data["data"]
    else:
        raise APIError(json_data)

def open_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/open", { uuid: uuid, remote_uuid: remote_uuid })
    return data

def stop_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/stop", { uuid: uuid, remote_uuid: remote_uuid })
    return data

def kill_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/kill", { uuid: uuid, remote_uuid: remote_uuid })
    return data

def restart_instance(uuid: str, remote_uuid: str):
    data = api_get(f"{base_url}/api/protected_instance/restart", { uuid: uuid, remote_uuid: remote_uuid })
    return data

def command_instance(uuid: str, remote_uuid: str, command: str):
    data = api_get(f"{base_url}/api/protected_instance/open", { uuid: uuid, remote_uuid: remote_uuid, command: command })
    return data
  
def get_instance(uuid: str, remote_uuid: str):
    # data.status 会返回的值及其解释：-1（状态未知）；0（已停止）；1（正在停止）；2（正在启动）；3（正在运行）
    data = api_get(f"{base_url}/api/instance", { uuid: uuid, remote_uuid: remote_uuid })
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
    source.reply("!!mcdm help")

@builder.command("!!mcdm list")
@builder.command("!!mcdm servers")
@builder.command("!!mcdm status")
def handle_list(source: CommandSource, context: CommandContext):
    text = ""
    for server in config["servers"]:
        instance = get_instance(server["uuid"], server["remote_uuid"])
        text += f"{server['name']:.20} - {server_status(instance['status'])}"
    source.reply(text)
  
@builder.command("!!mcdm start <server>")
def handle_start(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["name"])
    open_instance(server_config["uuid"], server_config["remote_id"])

@builder.command("!!mcdm stop <server>")
def handle_stop(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["name"])
    stop_instance(server_config["uuid"], server_config["remote_id"])
  
@builder.command("!!mcdm restart <server>")
def handle_restart(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["name"])
    restart_instance(server_config["uuid"], server_config["remote_id"])
  
@builder.command("!!mcdm sync <server>")
def handle_sync(source: CommandSource, context: CommandContext):
    server_config = get_server_config(context["name"])
    ... 

def registry_command(server: PluginServerInterface):
    """
        !!mcdm
        !!mcdm help
        !!mcdm list
        !!mcdm list
        !!mcdm servers
        !!mcdm start <server>
        !!mcdm stop <server>
        !!mcdm restart <server>
        !!mcdm sync <server>
    """

    # define your command nodes
    builder.arg('server', Text)

    # done, now register the commands to the server
    builder.register(server)

def on_load(server: PluginServerInterface, prev: PluginServerInterface | None):
    global client, config, base_url

    # load configurations
    conf_path = Path("./mcdm.yml")
    if (not (conf_path.exists() and conf_path.is_file())):
        logger.exception(f"config file {conf_path.absolute} not found.")
    with open(conf_path, "r", encoding="utf8") as f:
        config = yaml.load(f)
    client = requests.Session()
    client.headers = {
        config["apikey"]
    }
    base_url = 'http://127.0.0.1'
    # load configurations
    registry_command(server)