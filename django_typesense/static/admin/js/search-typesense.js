(function($) {
    $(document).ready(function () {
        const user_input = $("#searchbar");
        const post_user_input = $("#post_search_term");
        const delegates_div = $('#changelist-form');
        const endpoint = JSON.parse(document.getElementById('search_typesense').textContent);
        const delay_by_in_ms = 100;
        let scheduled_function = false;
        const urlParams = new URLSearchParams(window.location.search);

        function get_query(){
            var url = document.location.href;
            var qs = url.substring(url.indexOf('?') + 1).split('&');
            for(var i = 0, result = {}; i < qs.length; i++){
                qs[i] = qs[i].split('=');
                if (qs[i][1]) {
                    result[qs[i][0]] = decodeURIComponent(qs[i][1]);
                }
            }
            return result;
        }

        let ajax_call = function (endpoint, request_parameters) {
            $.getJSON(endpoint, request_parameters)
                .done(response => {
                    // fade out the delegates_div, then:
                    delegates_div.fadeTo('fast', 0.5).promise().then(() => {
                        // replace the HTML contents
                        delegates_div.html(response['html_from_view']);
                        // fade-in the div with new contents
                        delegates_div.fadeTo('fast', 1);
                        post_user_input.val(user_input.val());
                    })
                });
        };

        ajax_call(endpoint, Object.assign({search_query:''}, get_query()))

        user_input.on('keyup', function () {
            let user_input_val = $(this).val();
            const search_parameters = {
                search_query:user_input_val, // value of user_input: the HTML element with ID user-input
            };

            const request_parameters = Object.assign(search_parameters, get_query());

            delegates_div.html('<h1>Searching...</h1>');
            // if scheduled_function is NOT false, cancel the execution of the function
            if (scheduled_function) {
                clearTimeout(scheduled_function);
            }
            // setTimeout returns the ID of the function to be executed
            scheduled_function = setTimeout(ajax_call, delay_by_in_ms, endpoint, request_parameters);
        })
    });
})(django.jQuery);
