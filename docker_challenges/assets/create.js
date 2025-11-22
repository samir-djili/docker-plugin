CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
    $('a[href="#new-desc-preview"]').on('shown.bs.tab', function (event) {
        if (event.target.hash == '#new-desc-preview') {
            var editor_value = $('#new-desc-editor').val();
            $(event.target.hash).html(
                md.render(editor_value)
            );
        }
    });
    $(document).ready(function(){
    $('[data-toggle="tooltip"]').tooltip();
        
        CTFd.fetch("/api/v1/docker")
            .then(response => response.json())
            .then(result => {
                $.each(result['data'], function(i, item){
                    if (item.name == 'Error in Docker Config!') { 
                        document.docker_form.dockerimage_select.disabled = true;
                        $("label[for='DockerImage']").text('Docker Image ' + item.name)
                    }
                    else {
                        $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
                    }
                });
            })
            .catch(error => {
                console.error('Error fetching docker images:', error);
                document.docker_form.dockerimage_select.disabled = true;
                $("label[for='DockerImage']").text('Docker Image: Error loading images');
            });
        
        // Add form validation for connection type
        $('form[id="challenge-create-form"]').on('submit', function(e) {
            var connType = $('#conn_type').val();
            var validTypes = ['http', 'ssh', 'tcp'];
            
            if (!connType || connType === '') {
                e.preventDefault();
                alert('Please select a connection type for the Docker challenge.');
                $('#conn_type').focus();
                return false;
            }
            
            if (validTypes.indexOf(connType) === -1) {
                e.preventDefault();
                alert('Invalid connection type. Please select HTTP, SSH, or TCP.');
                $('#conn_type').focus();
                return false;
            }
        });
    });
});
