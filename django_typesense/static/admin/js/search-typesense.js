(function($) {
    $(document).ready(function () {
        let ajax_call = function (endpoint, request_parameters) {
            $.getJSON(endpoint, request_parameters)
                .done(response => {
                    changelist_form.fadeTo('fast', 0.5).promise().then(() => {
                        changelist_form.html($(response['html']).find('#changelist-form').html());
                        changelist_form.fadeTo('fast', 1);
                    })
                })
                .fail(function( jqxhr, textStatus, error ) {
                    const err = textStatus + ", " + error;
                    console.log( "Request Failed: " + err );
                    changelist_form.html('Sorry. An error occurred on our end.');
                });
        };

        const searchbar = $("#searchbar");
        const changelist_form = $('#changelist-form');
        const delay_by_in_ms = 0;
        const endpoint = window.location.origin + window.location.pathname
        let scheduled_function = false;

        searchbar.on('input', function () {
            const search_value = $(this).val().trim();
            const search_parameters = {q:search_value};
            const urlParams = new URLSearchParams(window.location.search);
            const request_parameters = Object.assign(search_parameters, urlParams);

            changelist_form.html('<h1>Searching...</h1>');
            if (scheduled_function) {
                clearTimeout(scheduled_function);
            }
            scheduled_function = setTimeout(ajax_call, delay_by_in_ms, endpoint, request_parameters);
        })
    });
})(django.jQuery);
