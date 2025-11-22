import requests, traceback, tempfile, random, string
from CTFd.models import db
from CTFd.utils.dates import unix_time
from datetime import datetime

from .config import NANO_CPUS_QUOTA, MEMORY_LIMIT, TOKEN_LENGTH
from .utils import log, update_haproxy, gen_subnet_from_ids
from .models import DockerConfig, DockerChallenge, DockerChallengeTracker


def do_request(endpoint, data=None, headers=None, method="GET"):
    api = get_docker_api()
    URL = f"{api}{endpoint}"
    cert = get_client_cert()
    timeout = 5
    try:
        if method == "GET":
            r = requests.get(
                url=URL, cert=cert, verify=False, headers=headers, timeout=timeout
            )
        elif method == "POST":
            r = requests.post(
                url=URL,
                json=data,
                cert=cert,
                verify=False,
                headers=headers,
                timeout=timeout,
            )
        elif method == "DELETE":
            r = requests.delete(
                url=URL, cert=cert, verify=False, headers=headers, timeout=timeout
            )
    except:
        print(traceback.print_exc())
        r = None
    return r


def get_client_cert():
    docker_config = DockerConfig.query.filter_by(id=1).first()
    if not docker_config.tls_enabled:
        return None
    try:
        ca = docker_config.ca_cert
        client = docker_config.client_cert
        ckey = docker_config.client_key
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(ca.encode())
        ca_file.seek(0)
        client_file = tempfile.NamedTemporaryFile(delete=False)
        client_file.write(client.encode())
        client_file.seek(0)
        key_file = tempfile.NamedTemporaryFile(delete=False)
        key_file.write(ckey.encode())
        key_file.seek(0)
        CERT = (client_file.name, key_file.name)
    except:
        print(traceback.print_exc())
        CERT = None
    return CERT


def get_docker_api():
    docker_config = DockerConfig.query.filter_by(id=1).first()
    http_prefix = "http" if not docker_config.tls_enabled else "https"
    api = f"{http_prefix}://{docker_config.hostname}"

    return api


def create_instance(image_name, session):
    # get the challenge
    challenge = DockerChallenge.query.filter_by(docker_image=image_name).first()
    log(f"instancing challenge {challenge.name}")
    # generate the random token to be used for the subdomain
    token = "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(TOKEN_LENGTH)
    ).lower()
    # generate the contaier name
    container_name = f"{token}-{image_name.split(':')[1]}"
    # generate the bridged network name and subnet
    network_name = f"net-{container_name}"
    subnet = gen_subnet_from_ids(session.id, challenge.id)
    # create the network and container
    create_network(network_name, subnet)
    msg = create_container(container_name, image_name, network_name)
    # start the container and grab its ip
    container_id = msg["Id"]
    start_container(container_id)
    container_info = inspect_container(container_id)
    container_ip = container_info["NetworkSettings"]["Networks"][network_name][
        "IPAddress"
    ]
    # add the instance to the db
    entry = DockerChallengeTracker(
        entity_id=session.id,
        docker_challenge_id=challenge.id,
        timestamp=unix_time(datetime.utcnow()),
        revert_time=unix_time(datetime.utcnow())
        + 300,  # this column is not used, so delete it
        instance_id=container_id,
        ports=",".join(get_required_ports(image_name)),
        subdomain=container_name,
        container_ip=container_ip,
    )
    db.session.add(entry)
    db.session.commit()
    # update haproxy
    update_haproxy()
    return


def delete_instance(instance_id):
    # get network name
    container_info = inspect_container(instance_id)
    network_name = list(container_info["NetworkSettings"]["Networks"].keys())[0]
    # delete the network and container
    delete_container(instance_id)
    delete_network(network_name)
    # delete the entry in the db
    DockerChallengeTracker.query.filter_by(instance_id=instance_id).delete()
    db.session.commit()
    # update haproxy
    update_haproxy()
    return


# For the Docker Config Page. Gets the Current Repositories available on the Docker Server.
def get_repositories(tags=False):
    r = do_request("/images/json?all=1")
    result = list()
    for i in r.json():
        if not i["RepoTags"] == None:
            if not i["RepoTags"][0].split(":")[0] == "<none>":
                if not tags:
                    result.append(i["RepoTags"][0].split(":")[0])
                else:
                    result.append(i["RepoTags"][0])
    return list(set(result))


def get_required_ports(image):
    r = do_request(f"/images/{image}/json?all=1")
    ports = r.json()["Config"]["ExposedPorts"].keys()
    return ports


def create_container(container_name, image, network_name):
    endpoint = f"/containers/create?name={container_name}"
    ports = {port: {} for port in get_required_ports(image)}
    data = {
        "Image": image,
        "ExposedPorts": ports,
        "HostConfig": {
            "NetworkMode": network_name,
            "Memory": MEMORY_LIMIT,
            "NanoCpus": NANO_CPUS_QUOTA,
        },
    }
    r = do_request(endpoint, data=data, method="POST")
    success, msg = r.status_code == 201, r.json()
    if not success:
        raise Exception(f"Could not create container: {msg['message']}")
    log(f"created container: {container_name}")
    return msg


def delete_container(container_id):
    r = do_request(f"/containers/{container_id}?force=true", method="DELETE")
    success = r.status_code == 204
    if not success:
        raise Exception(f"Could not delete container: {r.json()['message']}")
    log(f"deleted container: {container_id}")


def list_networks():
    endpoint = "/networks"
    r = do_request(endpoint)
    succes, msg = r.status_code == 200, r.json()
    if not succes:
        raise Exception("Could not list networks")
    return msg


def create_network(network_name, subnet, driver="bridge", delete_if_exists=True):
    endpoint = f"/networks/create"
    data = {
        "Name": network_name,
        "Driver": driver,
        "IPAM": {
            "Config": [
                {
                    "Subnet": subnet,
                }
            ],
        },
    }
    while True:
        r = do_request(endpoint, data=data, method="POST")
        success, msg = r.status_code == 201, r.json()
        if not success:
            log(msg["message"])
            if (
                delete_if_exists
                and "Pool" in msg["message"]
                and "overlaps" in msg["message"]
            ):
                for network in list_networks():
                    if (
                        len(network["IPAM"]["Config"]) > 0
                        and network["IPAM"]["Config"][0]["Subnet"] == subnet
                    ):
                        delete_network(network["Name"])
            else:
                raise Exception(f"Could not create network: {msg['message']}")
        else:
            break
    log(f"created network: {network_name} with subnet {subnet}")
    return msg


def delete_network(network_name):
    endpoint = f"/networks/{network_name}"
    r = do_request(endpoint, method="DELETE")
    success = r.status_code == 204
    if not success:
        raise Exception(f"Could not delete network: {r.json()['message']}")
    log(f"deleted network: {network_name}")


def start_container(container_id):
    endpoint = f"/containers/{container_id}/start"
    r = do_request(endpoint, method="POST")
    success = r.status_code in (204, 304)
    if not success:
        raise Exception(f"Could not start container: {r.json()['message']}")
    log(f"started container: {container_id}")


def inspect_container(container_id):
    log(f"inspecting container {container_id}")
    endpoint = f"/containers/{container_id}/json"
    r = do_request(endpoint)
    success, msg = r.status_code == 200, r.json()
    if not success:
        raise Exception(f"Could not inspect container: {msg['message']}")
    return msg
