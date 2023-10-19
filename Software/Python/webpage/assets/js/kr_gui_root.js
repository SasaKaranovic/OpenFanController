$.urlParam = function(name){
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null) {
       return null;
    }
    return decodeURI(results[1]) || 0;
}

// When page is loaded
$(function () {

    // Handle dynamic includes
    var includes = $('[data-include]')
    $.each(includes, function () {
        var file = 'views/' + $(this).data('include') + '.html'
        $(this).load(file)
    })
})


function create_toast(toast_title, toast_message)
{
    var toast = '\
                    <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="false" data-bs-toggle="toast">\
                    <div class="toast-header">\
                    <strong class="me-auto">'+ toast_title +'</strong>\
                    <button type="button" class="ms-2 btn-close" data-bs-dismiss="toast" aria-label="Close"></button>\
                    </div>\
                    <div class="toast-body">\
                    '+ toast_message +'\
                    </div>\
                    </div>';
    $("#content").append(toast);
}
