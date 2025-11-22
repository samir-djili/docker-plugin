CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
    $(document).ready(function() {
        $.getJSON("/api/v1/docker", function(result) {
            $.each(result['data'], function(i, item) {
                $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
            });
            $("#dockerimage_select").val(DOCKER_IMAGE).change();
	    // Set the connection type if it exists
            if (typeof CONN_TYPE !== 'undefined' && CONN_TYPE) {
                $("#conn_type").val(CONN_TYPE);
            }
        });
        // Add form validation for connection type
        $('form[id="challenge-update-form"]').on('submit', function(e) {
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
