import traceback
from CTFd.models import db, Teams, Users
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.utils.user import get_current_team
from CTFd.utils.user import get_current_user
from CTFd.utils.config import is_teams_mode
from flask_restx import Namespace, Resource
from flask import request, Blueprint, abort, render_template
from CTFd.utils.dates import unix_time
from datetime import datetime
from wtforms import (
    FileField,
    HiddenField,
    RadioField,
    StringField,
    SelectMultipleField,
)
from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField

from .docker_api import get_repositories, delete_instance, create_instance
from .models import DockerChallengeTracker, DockerChallenge, DockerConfig
from .config import *


kill_container = Namespace("nuke", description="Endpoint to nuke containers")
container_namespace = Namespace(
    "container", description="Endpoint to interact with containers"
)
active_docker_namespace = Namespace(
    "docker", description="Endpoint to retrieve User Docker Image Status"
)
docker_namespace = Namespace("docker", description="Endpoint to retrieve dockerstuff")


@kill_container.route("", methods=["POST", "GET"])
class KillContainerAPI(Resource):
    @admins_only
    def get(self):
        container_id = request.args.get("container")
        all = request.args.get("all")
        current_instances = DockerChallengeTracker.query.all()
        try:
            if all == "true":
                for ins in current_instances:
                    delete_instance(ins.instance_id)
            elif container_id != "null" and container_id in [
                ins.instance_id for ins in current_instances
            ]:
                delete_instance(container_id)
            else:
                return False

            return True
        except:
            return False


@container_namespace.route("", methods=["POST", "GET"])
class ContainerAPI(Resource):
    @authed_only
    # I wish this was Post... Issues with API/CSRF and whatnot. Open to a Issue solving this.
    def get(self):
        image = request.args.get("name")
        authorized_images = [
            chall.docker_image for chall in DockerChallenge.query.all()
        ]
        if not image or image not in authorized_images:
            return abort(403)
        session = get_current_team() if is_teams_mode() else get_current_user()
        challenge = DockerChallenge.query.filter_by(docker_image=image).first()

        # First we'll delete all old docker containers (+2 hours)
        containers = DockerChallengeTracker.query.filter_by(entity_id=session.id)
        for i in containers:
            if (
                unix_time(datetime.utcnow()) - int(i.timestamp)
            ) >= MAX_INSTANCE_LIFE_IN_SEC:
                delete_instance(i.instance_id)
        check = (
            DockerChallengeTracker.query.filter_by(entity_id=session.id)
            .filter_by(docker_challenge_id=challenge.id)
            .first()
        )

        # If this container is already created, we don't need another one.
        if (
            check != None
            and (unix_time(datetime.utcnow()) - int(check.timestamp)) < 300
        ):
            return abort(403)
        # The exception would be if we are reverting a box. So we'll delete it if it exists and has been around for more than 5 minutes.
        elif check != None:
            delete_instance(check.instance_id)

        container_info = create_instance(image, session)  # , portsbl)
        # return if successfull
        return


@active_docker_namespace.route("", methods=["POST", "GET"])
class DockerStatus(Resource):
    """
    The Purpose of this API is to retrieve a public JSON string of all docker containers
    in use by the current team/user.
    """

    @authed_only
    def get(self):
        session = get_current_team() if is_teams_mode() else get_current_user()
        tracker = DockerChallengeTracker.query.filter_by(entity_id=session.id)
        data = list()
        for i in tracker:
            chall = DockerChallenge.query.filter_by(id=i.docker_challenge_id).first()
            data.append(
                {
                    "id": i.id,
                    "docker_image": chall.docker_image,
                    "timestamp": i.timestamp,
                    "revert_time": i.revert_time,
                    "host": f"{i.subdomain}.{DOMAIN_NAME}",
                    "conn_type": chall.conn_type,
                }
            )
        return {"success": True, "data": data}


@docker_namespace.route("", methods=["POST", "GET"])
class DockerAPI(Resource):
    """
    This is for creating Docker Challenges. The purpose of this API is to populate the Docker Image Select form
    object in the Challenge Creation Screen.
    """

    @admins_only
    def get(self):
        images = get_repositories(tags=True)
        if images:
            data = list()
            for i in images:
                data.append({"name": i})
            return {"success": True, "data": data}
        else:
            return {
                "success": False,
                "data": [{"name": "No images available or could not fetch them"}],
            }, 400


def define_docker_admin(app):
    admin_docker_config = Blueprint(
        "admin_docker_config",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
        docker = DockerConfig.query.filter_by(id=1).first()
        form = DockerConfigForm()
        if request.method == "POST":
            if docker:
                b = docker
            else:
                b = DockerConfig()
            try:
                ca_cert = request.files["ca_cert"].stream.read()
            except:
                print(traceback.print_exc())
                ca_cert = ""
            try:
                client_cert = request.files["client_cert"].stream.read()
            except:
                print(traceback.print_exc())
                client_cert = ""
            try:
                client_key = request.files["client_key"].stream.read()
            except:
                print(traceback.print_exc())
                client_key = ""
            if len(ca_cert) != 0:
                b.ca_cert = ca_cert
            if len(client_cert) != 0:
                b.client_cert = client_cert
            if len(client_key) != 0:
                b.client_key = client_key
            b.hostname = request.form["hostname"]
            b.tls_enabled = request.form["tls_enabled"]
            if b.tls_enabled == "True":
                b.tls_enabled = True
            else:
                b.tls_enabled = False
            if not b.tls_enabled:
                b.ca_cert = None
                b.client_cert = None
                b.client_key = None
            try:
                b.repositories = ",".join(
                    request.form.to_dict(flat=False)["repositories"]
                )
            except:
                print(traceback.print_exc())
                b.repositories = None
            db.session.add(b)
            db.session.commit()
            docker = DockerConfig.query.filter_by(id=1).first()
        try:
            repos = get_repositories()
        except:
            print(traceback.print_exc())
            repos = list()
        if len(repos) == 0:
            form.repositories.choices = [("ERROR", "Failed to Connect to Docker")]
        else:
            form.repositories.choices = [(d, d) for d in repos]
        dconfig = DockerConfig.query.first()
        try:
            selected_repos = dconfig.repositories
            if selected_repos == None:
                selected_repos = list()
        # selected_repos = dconfig.repositories.split(',')
        except:
            print(traceback.print_exc())
            selected_repos = []
        return render_template(
            "docker_config.html", config=dconfig, form=form, repos=selected_repos
        )

    app.register_blueprint(admin_docker_config)


def define_docker_status(app):
    admin_docker_status = Blueprint(
        "admin_docker_status",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        Entity = Teams if is_teams_mode() else Users
        docker_tracker = (
            DockerChallengeTracker.query.join(
                DockerChallenge,
                DockerChallenge.id == DockerChallengeTracker.docker_challenge_id,
            )
            .join(Entity, Entity.id == DockerChallengeTracker.entity_id)
            .with_entities(
                DockerChallenge.name,
                Entity.name.label("entity_name"),
                DockerChallengeTracker.id,
                DockerChallengeTracker.instance_id,
            )
            .all()
        )
        return render_template("admin_docker_status.html", dockers=docker_tracker)

    app.register_blueprint(admin_docker_status)


class DockerConfigForm(BaseForm):
    id = HiddenField()
    hostname = StringField(
        "Docker Hostname", description="The Hostname/IP and Port of your Docker Server"
    )
    tls_enabled = RadioField("TLS Enabled?")
    ca_cert = FileField("CA Cert")
    client_cert = FileField("Client Cert")
    client_key = FileField("Client Key")
    repositories = SelectMultipleField("Repositories")
    submit = SubmitField("Submit")
