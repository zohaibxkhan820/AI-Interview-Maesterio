// Function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Set up CSRF token for all AJAX requests
document.addEventListener('DOMContentLoaded', function() {
    const csrftoken = getCookie('csrftoken');
    
    if (csrftoken) {
        // Add CSRF token to all AJAX requests
        const originalFetch = window.fetch;
        window.fetch = function() {
            const args = Array.from(arguments);
            if (args[1] && args[1].method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(args[1].method.toUpperCase())) {
                if (!args[1].headers) {
                    args[1].headers = {};
                }
                // Check if headers is a Headers object and convert it to a plain object if necessary
                if (args[1].headers instanceof Headers) {
                    const plainHeaders = {};
                    for (const [key, value] of args[1].headers.entries()) {
                        plainHeaders[key] = value;
                    }
                    args[1].headers = plainHeaders;
                }
                args[1].headers['X-CSRFToken'] = csrftoken;
            }
            return originalFetch.apply(window, args);
        };

        // For jQuery AJAX requests (if using jQuery)
        if (typeof jQuery !== 'undefined') {
            jQuery.ajaxSetup({
                beforeSend: function(xhr, settings) {
                    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(settings.type.toUpperCase())) {
                        xhr.setRequestHeader("X-CSRFToken", csrftoken);
                    }
                }
            });
        }
    }
}); 