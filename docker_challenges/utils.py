import jinja2
import os
import subprocess

from os import path
from CTFd.models import Challenges

from .models import DockerChallengeTracker, DockerChallenge
from .config import *


SCRIPT_ROOT = path.dirname(__file__)
JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(path.join(SCRIPT_ROOT, TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

# ssh/scp


# scp local to remote with roovb
def scp_l2r(localpath, remotepath, user, instance):
    # Debug: Check if key file exists and permissions
    if not os.path.exists(PROFILE_KEY_PATH):
        log(f"ERROR: SSH key file not found at {PROFILE_KEY_PATH}", warn=True)
        return False
    
    log(f"Using SSH key: {PROFILE_KEY_PATH}")
    log(f"Copying {localpath} to {user}@{instance}:{remotepath}")
    
    result = subprocess.run(
        [
            "scp",
            "-i",
            PROFILE_KEY_PATH,
            "-o",
            "StrictHostKeyChecking=no",
            "-v",  # verbose for debugging
            localpath,
            f"{user}@{instance}:{remotepath}",
        ],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        log(f"SCP failed with return code {result.returncode}", warn=True)
        log(f"STDERR: {result.stderr}", warn=True)
        log(f"STDOUT: {result.stdout}", warn=True)
    else:
        log("SCP successful")
    
    return result.returncode == 0

# run command through ssh
def ssh_cmd(user, instance, cmd):
    return (
        subprocess.run(
            [ "ssh","-i",PROFILE_KEY_PATH, f"{user}@{instance}", cmd]
        ).returncode
        == 0
    )


def gen_subnet_from_ids(team_id, chall_id):
    SUBNET_FORMAT = "1{team_id_msb}.1{team_id_lsb}.{chall_id}.0/30"  # example: if team_id = 1475 and challenge_id = 45 then 147.175.45.0/4
    id = f"{team_id:04}"
    part1, part2 = id[:2], id[2:]
    return SUBNET_FORMAT.format(team_id_msb=part1, team_id_lsb=part2, chall_id=chall_id)


def log(data, inform=True, warn=False):
    msg = "[!] " if warn else "[*] "
    msg += str(data)
    print(msg)


SCRIPT_ROOT = path.dirname(__file__)
JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(path.join(SCRIPT_ROOT, TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


# adjust it to raise exception if something goes wrong
def update_haproxy():
    log("Updating haproxy config ...")
    containers = (
        DockerChallengeTracker.query.join(
            DockerChallenge,
            DockerChallenge.id == DockerChallengeTracker.docker_challenge_id,
        )
        .with_entities(
            DockerChallenge.conn_type,
            DockerChallengeTracker.ports,
            DockerChallengeTracker.subdomain,
            DockerChallengeTracker.container_ip,
        )
        .all()
    )

    if not os.path.exists(HAPROXY_CFG_DIR):
        os.mkdir(HAPROXY_CFG_DIR)

    # update the configuration
    template = JINJA_ENV.get_template(HAPROXY_CFG_TEMP_PATH)
    content = template.render(
        {
            "containers": containers,
            "SNI_MAP_RMT_PATH": SNI_MAP_RMT_PATH,
            "STATS_PORT": STATS_PORT,
            "STATS_USER": STATS_USER,
            "STATS_PASSWORD": STATS_PASSWORD,
            "SSL_CERT_PATH": SSL_CERT_PATH,
            "INTERNAL_INSTANCE_IP": INTERNAL_INSTANCE_IP,
            "AUTO_BAN": AUTO_BAN,
        }
    )
    filename = f"{HAPROXY_CFG_DIR}/{HAPROXY_CFG_PATH}"
    with open(filename, "w") as f:
        f.write(content)
    scp_l2r(filename, HAPROXY_CFG_RMT_PATH, USER, INTERNAL_INSTANCE_IP)

    # update the sni_map file
    template = JINJA_ENV.get_template(SNI_MAP_TEMP_PATH)
    content = template.render(
        {
            "containers": containers,
        }
    )
    filename = f"{HAPROXY_CFG_DIR}/{SNI_MAP_PATH}"
    with open(f"{HAPROXY_CFG_DIR}/{SNI_MAP_PATH}", "w") as f:
        f.write(content)
    scp_l2r(filename, SNI_MAP_RMT_PATH, USER, INTERNAL_INSTANCE_IP)

    log("Updated haproxy config, reloading the server ...")
    # upload the files to the docker VM
    ssh_cmd(USER, INTERNAL_INSTANCE_IP, "sudo systemctl reload haproxy")
