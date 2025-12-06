from CTFd.models import db, Challenges


class DockerConfig(db.Model):
    """
    Docker Config Model. This model stores the config for docker API connections.
    """
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column("hostname", db.String(64), index=True)
    tls_enabled = db.Column("tls_enabled", db.Boolean, default=False, index=True)
    ca_cert = db.Column("ca_cert", db.String(2200), index=True)
    client_cert = db.Column("client_cert", db.String(2000), index=True)
    client_key = db.Column("client_key", db.String(3300), index=True)
    repositories = db.Column("repositories", db.String(1024), index=True)
    enable_instance_limit = db.Column("enable_instance_limit", db.Boolean, default=False, index=True)
    max_instances_per_team = db.Column("max_instances_per_team", db.Integer, default=3, index=True)


class DockerChallengeTracker(db.Model):
    """
    Docker Container Tracker. This model stores the users/teams active docker containers.
    """
    id = db.Column(db.Integer, primary_key=True)
    entity_id = db.Column("entity_id", db.String(64), index=True)
    docker_challenge_id = db.Column(
        None, db.ForeignKey("docker_challenge.id"), index=True
    )
    timestamp = db.Column("timestamp", db.Integer, index=True)
    revert_time = db.Column("revert_time", db.Integer, index=True)
    instance_id = db.Column("instance_id", db.String(128), index=True)
    ports = db.Column("ports", db.String(128), index=True)
    subdomain = db.Column("subdomain", db.String(1024), index=True)
    container_ip = db.Column("container_ip", db.String(32), index=True)


class DockerChallenge(Challenges):
    __mapper_args__ = {"polymorphic_identity": "docker"}
    id = db.Column(None, db.ForeignKey("challenges.id"), primary_key=True)
    docker_image = db.Column(db.String(128), index=True)
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay = db.Column(db.Integer, default=0)
    conn_type = db.Column(db.String(10), index=True)
    dynamic_score = db.Column(db.Boolean, default=False)
