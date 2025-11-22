# CTFd Docker Challenges Plugin

A CTFd plugin that enables dynamic Docker container deployment for CTF challenges with automatic HAProxy routing and SNI-based access.

## Overview

This plugin extends CTFd to support Docker-based challenges where each team/user gets an isolated container instance with unique routing. Containers are created on-demand, automatically routed via HAProxy with SNI mapping, and cleaned up after a configurable lifetime.

## Architecture

```
CTFd Server
    ├─ Docker Challenges Plugin
    │   ├─ Challenge Type (create/update/view)
    │   ├─ API Routes (/api/v1/container, /api/v1/docker_status)
    │   └─ Admin Pages (config, status monitoring)
    │
    ├─ Docker API Client (TLS)
    │   └─ Manages containers & networks on remote Docker host
    │
    └─ HAProxy Integration
        ├─ Generates haproxy.cfg + sni.map
        ├─ SSH/SCP to HAProxy VM
        └─ Reloads HAProxy on container start/stop
```

### Data Flow

1. **User clicks "Start Docker Instance"** → `POST /api/v1/container?name=<image>`
2. **Plugin creates**:
   - Unique subdomain token (15 chars)
   - Isolated bridge network with generated subnet
   - Docker container with resource limits
3. **Plugin updates**:
   - Database tracker (`DockerChallengeTracker`)
   - HAProxy config via Jinja2 templates
   - Remote HAProxy via SSH/SCP → reload
4. **User accesses**: `https://<token>-<image>.instances.domain.com`
5. **HAProxy routes** via SNI map → container IP:port
6. **Cleanup**: Containers older than 2 hours auto-deleted; revert cooldown 5 minutes

## Components

### Core Files

| File | Purpose |
|------|---------|
| `__init__.py` | Plugin entry point, challenge type registration |
| `models.py` | Database models (DockerChallenge, DockerChallengeTracker, DockerConfig) |
| `docker_api.py` | Docker API client (create/delete containers, networks) |
| `routes.py` | API routes & admin pages |
| `utils.py` | HAProxy config generation, SSH/SCP helpers |
| `config.py` | Configuration constants (domain, limits, paths) |

### Frontend Assets

| File | Purpose |
|------|---------|
| `assets/view.js` | Challenge view: status polling, start/revert containers |
| `assets/create.js` | Admin: create challenge with Docker image |
| `assets/update.js` | Admin: update challenge settings |
| `templates/*.html` | Jinja2 templates for admin pages |

### HAProxy Templates

| File | Purpose |
|------|---------|
| `haproxy/templates/haproxy.cfg.j2` | Main HAProxy config with TLS, frontends, backends |
| `haproxy/templates/sni.map.j2` | SNI-to-backend mapping for subdomain routing |

## Setup

### Prerequisites

- CTFd 3.6.0+
- Remote Docker host with API access (TCP/TLS)
- HAProxy VM with SSH access
- Wildcard SSL cert for `*.instances.domain.com`

### Installation

1. **Clone plugin into CTFd plugins directory**:
   ```bash
   cd CTFd/plugins
   git clone <repo-url> docker_challenges
   ```

2. **Configure plugin** (`config.py`):
   ```python
   DOMAIN_NAME = "instances.yourdomain.com"
   INTERNAL_INSTANCE_IP = "10.x.x.x"  # HAProxy VM IP
   USER = "your_ssh_user"
   PROFILE_KEY_PATH = "/path/to/ssh_key"
   
   # Resource limits
   MEMORY_LIMIT = 104857600  # 100MB
   NANO_CPUS_QUOTA = 50000000  # 0.05 CPU
   MAX_INSTANCE_LIFE_IN_SEC = 7200  # 2 hours
   ```

3. **Setup HAProxy VM**:
   - Install HAProxy
   - Place wildcard SSL cert at `/etc/haproxy/certs/<domain>.pem`
   - Ensure SSH key access for CTFd → HAProxy
   - Create `/etc/haproxy/sni.map` (will be managed by plugin)

4. **Restart CTFd**:
   ```bash
   docker-compose restart
   ```

### Admin Configuration

1. **Navigate to** `/admin/docker_config`
2. **Set Docker host**:
   - Hostname: `docker.host.com:2376`
   - TLS Enabled: `True`
   - Upload CA cert, client cert, client key
3. **Select repositories** (images available for challenges)
4. **Save**

## Usage

### Creating a Docker Challenge

1. **Admin Panel** → **Challenges** → **Create**
2. **Select type**: `docker`
3. **Fill fields**:
   - Name, category, description, flags (standard CTFd)
   - **Docker Image**: Select from dropdown (populated from Docker host)
   - **Connection Type**: `http`, `ssh`, or `tcp`
   - **Dynamic Scoring** (optional): Initial/minimum value, decay
4. **Save**

### User Experience

1. **View challenge** → Shows "Start Docker Instance" button
2. **Click Start** → Container creates (~20s), connection info appears:
   - **HTTP**: `https://<token>-<image>.instances.domain.com`
   - **SSH**: `ssh ctf@<subdomain> -o ProxyCommand="..."`
   - **TCP**: `ncat --ssl <subdomain> 443`
3. **Revert cooldown**: 5 minutes between reverts (countdown shown)
4. **Auto-cleanup**: Containers deleted after 2 hours

### Admin Monitoring

- **Navigate to** `/admin/docker_status`
- **View active containers**: Challenge name, user/team, instance ID
- **Manual deletion**: Click "Kill" to remove specific containers

## Configuration Reference

### Environment Variables (config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_NAME` | `instances.domain.com` | Base domain for container subdomains |
| `INTERNAL_INSTANCE_IP` | - | HAProxy VM internal IP |
| `USER` / `PASSWD` | - | SSH credentials for HAProxy VM |
| `PROFILE_KEY_PATH` | - | SSH private key path |
| `MEMORY_LIMIT` | 104857600 | Container RAM limit (bytes) |
| `NANO_CPUS_QUOTA` | 50000000 | Container CPU limit (nanoseconds) |
| `MAX_INSTANCE_LIFE_IN_SEC` | 7200 | Max container lifetime (2 hours) |
| `TOKEN_LENGTH` | 15 | Subdomain token length |
| `AUTO_BAN` | False | HAProxy rate limiting (50 conn/min) |

### Database Models

#### DockerChallenge
- Extends `Challenges` with `docker_image`, `conn_type`, dynamic scoring

#### DockerChallengeTracker
- Tracks active containers: `entity_id`, `instance_id`, `subdomain`, `container_ip`, `timestamp`, `revert_time`

#### DockerConfig
- Stores Docker API credentials, hostname, TLS certs

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/docker_status` | GET | User | List user's active containers |
| `/api/v1/container?name=<image>` | GET | User | Start/revert container |
| `/api/v1/docker` | GET | Admin | List available Docker images |
| `/api/v1/nuke?container=<id>` | GET | Admin | Kill specific container |
| `/api/v1/nuke?all=true` | GET | Admin | Kill all containers |

## Network Isolation

Each container gets a unique `/30` bridge network:
- **Subnet format**: `1{team_id_msb}.1{team_id_lsb}.{challenge_id}.0/30`
- **Example**: Team 1475, Challenge 45 → `147.175.45.0/30`
- **Purpose**: Network isolation between teams, prevents container-to-container communication

## HAProxy Routing

### SNI Mapping
```
<token>-<image>.instances.domain.com → backend be_<token>-<image>
```

### Backend Generation
- **HTTP challenges**: `mode http`, health check `HEAD /`
- **TCP/SSH challenges**: `mode tcp`, TCP health checks
- **Load balancing**: Round-robin / least connections

### Auto-ban (Optional)
When `AUTO_BAN=True`:
- Limits: 50 connections/min, 50 concurrent connections per IP
- Tracks via HAProxy stick table (2-minute expiry)

## Troubleshooting

### Containers not accessible after creation
- **Check HAProxy reload**: SSH to HAProxy VM, `systemctl status haproxy`
- **Verify SNI map**: `cat /etc/haproxy/sni.map`
- **DNS**: Ensure wildcard DNS `*.instances.domain.com` → HAProxy IP
- **SSL**: Verify wildcard cert includes SNI names

### "Fetching information..." stuck
- **Fixed in latest version**: Removed unconditional 20s delay
- **Check**: Browser console for API errors at `/api/v1/docker_status`

### SSH/SCP to HAProxy fails
- **Verify key**: `ssh -i <key> user@haproxy-ip "echo OK"`
- **Check paths**: `PROFILE_KEY_PATH` exists, `HAPROXY_CFG_RMT_PATH` writable
- **Permissions**: `chmod 600 <key>`, HAProxy user has `sudo` for `systemctl reload haproxy`

### Docker API connection fails
- **TLS**: Verify certs uploaded in `/admin/docker_config`
- **Network**: Test `curl -k --cert client.crt --key client.key https://docker-host:2376/containers/json`
- **Firewall**: Docker host allows TCP 2376 from CTFd server

## Security Considerations

- **Resource limits**: Prevent DoS via `MEMORY_LIMIT`, `NANO_CPUS_QUOTA`
- **Network isolation**: Each container in isolated `/30` subnet
- **Auto-cleanup**: 2-hour max lifetime prevents abandoned containers
- **Revert cooldown**: 5-minute limit prevents spam
- **TLS**: Docker API and HAProxy routing use TLS
- **Rate limiting**: Optional `AUTO_BAN` for HAProxy

## Development

### Adding new connection types
1. Update `models.py`: Add type to `conn_type` field
2. Update `assets/view.js`: Add connection string format
3. Update `haproxy.cfg.j2`: Add routing logic

### Custom cleanup logic
- Modify `routes.py` → `ContainerAPI.get()` cleanup section
- Adjust `MAX_INSTANCE_LIFE_IN_SEC` in `config.py`

### Testing
```bash
# List active containers
curl -X GET https://ctfd.domain/api/v1/docker_status \
  -H "Authorization: Bearer <token>"

# Start container
curl -X GET "https://ctfd.domain/api/v1/container?name=<image>" \
  -H "Authorization: Bearer <token>"
```


