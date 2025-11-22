// Prevent multiple declarations if script is loaded multiple times
if (typeof window.INST_PORT_PLACEHOLDER === 'undefined') {
    window.INST_PORT_PLACEHOLDER = "${INSTANCE_PORT}";
}
if (typeof window.DELAY_SECONDS === 'undefined') {
    window.DELAY_SECONDS = 20;
}
if (typeof window.connection_info === 'undefined') {
    window.connection_info = null;
}
// Track if we just started/reverted a container to optionally delay UI until routing updates
if (typeof window.JUST_STARTED === 'undefined') {
    window.JUST_STARTED = false;
}

// CTFd challenge object must be initialized immediately (outside any guards)
CTFd._internal.challenge.data = undefined;

CTFd._internal.challenge.preRender = function() {
    // This function is required by CTFd 3.6.0
};

CTFd._internal.challenge.postRender = function() {
    const containername = CTFd._internal.challenge.data.docker_image;
    get_docker_status(containername);
};

CTFd._internal.challenge.submit = function(preview) {
    var challenge_id = parseInt(CTFd.lib.$('#challenge-id').val());
    var submission = CTFd.lib.$('#challenge-input').val();

    var body = {
        'challenge_id': challenge_id,
        'submission': submission,
    };
    var params = {};
    if (preview) {
        params['preview'] = true;
    }

    return CTFd.api.post_challenge_attempt(params, body).then(function(response) {
        if (response.status === 429) {
            // User was ratelimited but process response
            return response;
        }
        if (response.status === 403) {
            // User is not logged in or CTF is paused.
            return response;
        }
        return response;
    });
};

// Only initialize helper functions if not already done
if (typeof window.dockerChallengeInitialized === 'undefined') {
    window.dockerChallengeInitialized = true;

// Add String.format method if it doesn't exist
if (!String.prototype.format) {
    String.prototype.format = function() {
        var args = arguments;
        return this.replace(/{(\d+)}/g, function(match, number) { 
            return typeof args[number] != 'undefined'
                ? args[number]
                : match
            ;
        });
    };
}

function get_docker_status(container) {    
    CTFd.lib.$('#docker_container').html('<div class="text-center"><span>Fetching information... </span><br><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
    CTFd.fetch("/api/v1/docker_status").then(response => response.json()).then(result => {
        let running = false;
        CTFd.lib.$.each(result['data'], function(i, item) {
            if (item.docker_image == container) {
                running = true;
                const renderInfo = () => {
                    var data = '';
                    if (item.conn_type == 'http')
                        data = 'https://' + item.host + '<br />';
                    else if (item.conn_type == 'ssh')
                        data = 'ssh ctf@' + item.host + ' -o ProxyCommand="openssl s_client -quiet -connect ' + item.host + ':443 -servername ' + item.host + '" <br />';
                    else 
                        data = 'ncat -v --ssl ' + item.host + ' 443 ' + '<br />';
                    
                    CTFd.lib.$('#docker_container').html('<pre>Instance Information:<br />' + data + '<div class="mt-2" id="' + String(item.id).substring(0,10) + '_revert_container"></div>');
                    var countDownDate = new Date(parseInt(item.revert_time) * 1000).getTime();
                    var x = setInterval(function() {
                        var now = new Date().getTime();
                        var distance = countDownDate - now;
                        var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                        var seconds = Math.floor((distance % (1000 * 60)) / 1000);
                        if (seconds < 10) {
                            seconds = "0" + seconds;
                        }
                        CTFd.lib.$("#" + String(item.id).substring(0,10) + "_revert_container").html('Next Revert Available in ' + minutes + ':' + seconds);
                        if (distance < 0) {
                            clearInterval(x);
                            CTFd.lib.$("#" + String(item.id).substring(0,10) + "_revert_container").html('<a onclick="start_container(\'' + item.docker_image + '\');" class=\'btn btn-dark\'><small style=\'color:white;\'><i class="fas fa-redo"></i> Revert</small></a>');
                        }
                    }, 1000);
                };
                if (window.JUST_STARTED && window.DELAY_SECONDS > 0) {
                    setTimeout(() => { window.JUST_STARTED = false; renderInfo(); }, window.DELAY_SECONDS * 1000);
                } else {
                    renderInfo();
                }
                return false;
            }
        });
        if (!running) {
            CTFd.lib.$('#docker_container').html('<span><a onclick="start_container(\''+ container + '\');" class="btn btn-dark"><small style="color:white;"><i class="fas fa-play"></i> Start Docker Instance</small></a></span>');
        }
    }).catch(error => {
        console.error('Error fetching docker status:', error);
        CTFd.lib.$('#docker_container').html('<span>Error loading docker status</span>');
    });
}

function start_container(container) {
    if (window.connection_info === null) {
        window.connection_info = CTFd.lib.$('.challenge-connection-info code').text();
    } else {
        CTFd.lib.$('.challenge-connection-info code').text(window.connection_info);
    }
    CTFd.lib.$('#docker_container').html('<div class="text-center"><span>Creating instance... (this can take up to 1 minute)</span><br><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
    
    // Use CTFd.fetch with proper authentication and CSRF token
    CTFd.fetch("/api/v1/container?name=" + encodeURIComponent(container), {
        method: "GET",
        credentials: "same-origin",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    })
        .then(response => {
            if (response.ok) {
                // mark that we just started so we can optionally delay to let routing/proxy update
                window.JUST_STARTED = true;
                get_docker_status(container);
            } else if (response.status === 403) {
                throw new Error('Permission denied - you may need to wait before creating another container');
            } else {
                throw new Error('Container creation failed');
            }
        })
        .catch(error => {
            console.error('Error starting container:', error);
            ezal({
                title: "Attention!",
                body: "You can only revert a container once per 5 minutes! Please be patient.",
                button: "Got it!"
            });
            get_docker_status(container);
        });
}

var modal =
    '<div class="modal fade" tabindex="-1" role="dialog">' +
    '  <div class="modal-dialog" role="document">' +
    '    <div class="modal-content">' +
    '      <div class="modal-header">' +
    '        <h5 class="modal-title">{0}</h5>' +
    '        <button type="button" class="close" data-dismiss="modal" aria-label="Close">' +
    '          <span aria-hidden="true">&times;</span>' +
    "        </button>" +
    "      </div>" +
    '      <div class="modal-body">' +
    "        <p>{1}</p>" +
    "      </div>" +
    '      <div class="modal-footer">' +
    "      </div>" +
    "    </div>" +
    "  </div>" +
    "</div>";

function ezal(args) {
    var res = modal.format(args.title, args.body);
    var obj = CTFd.lib.$(res);
    var button = '<button type="button" class="btn btn-primary" data-dismiss="modal">{0}</button>'.format(
        args.button
    );
    obj.find(".modal-footer").append(button);
    CTFd.lib.$("main").append(obj);

    obj.modal("show");

    CTFd.lib.$(obj).on("hidden.bs.modal", function(e) {
        CTFd.lib.$(this).modal("dispose");
    });

    return obj;
}

} // End of dockerChallengeInitialized check
