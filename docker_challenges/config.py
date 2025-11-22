# Memory limit in bytes
MEMORY_LIMIT = 104857600
# CPU quota in units of 10^-9 CPUs
NANO_CPUS_QUOTA = 50000000
MAX_INSTANCE_LIFE_IN_SEC = 7200
# Cleanup interval in seconds (how often to check for expired containers)
CLEANUP_INTERVAL_SEC = 300  # 5 minutes

DOMAIN_NAME = "instances.samir.shellmates.club"  # instances.ctf.shellmates.club
#INTERNAL_INSTANCE_IP = ""
INSTANCE_NAME = "instance-20250920-211638"
INSTANCE_ZONE = "us-central1-c"
INTERNAL_INSTANCE_IP = "10.128.0.4"
USER = "ns_djili"
PASSWD = "shellmate"
PROFILE_KEY_PATH = "/home/ns_djili/.ssh/vm1_key"

STATS_PORT = 8080
STATS_USER = "shellmate"
STATS_PASSWORD = ""

TEMPLATES_DIR = "haproxy/templates"

HAPROXY_CFG_DIR = "/tmp/haproxy-config/"
HAPROXY_CFG_PATH = "haproxy.cfg"
HAPROXY_CFG_TEMP_PATH = "haproxy.cfg.j2"
HAPROXY_CFG_RMT_PATH = "/etc/haproxy/haproxy.cfg"

SNI_MAP_PATH = "sni.map"
SNI_MAP_TEMP_PATH = "sni.map.j2"
SNI_MAP_RMT_PATH = "/etc/haproxy/sni.map"

SSL_CERT_PATH = f"/etc/haproxy/certs/{DOMAIN_NAME}.pem"

TOKEN_LENGTH = 15
AUTO_BAN = False
