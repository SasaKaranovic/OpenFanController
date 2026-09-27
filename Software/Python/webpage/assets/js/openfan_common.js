// When page is loaded
$(function() {
{% if board['has_profiles'] %}
    ui_list_available_profiles();
{% end %}
    radio_control_via_rpm_handler();

    $("#fan_value").on("input change", function() {
        update_value_slider();
    } );

    $("#control_via_rpm").on("input change", function() {
        radio_control_via_rpm_handler();
    });

    $("#update_fan").on("click", function() {
        var fan = $("#fan_index").val();
        var percent = $("#fan_value").val();
        update_fan(fan, percent);
    } );

    $("#update_fan").on("click", function() {
        var fan = $("#fan_index").val();
        var percent = $("#fan_value").val();
        update_fan(fan, percent);
    } );

    $(".fan-name").on("dblclick", function(e) {
        var id = $(this).attr('id');
        id = id.replace("fan-", "");
        id = id.replace("-name", "");
        rename_device(id);
    } );

    gui_update_fan_aliases();

    // Periodic fan RPM update
    const interval = setInterval(function() {
       gui_update_fan_status();

{% if board['has_sensors'] %}
       gui_update_temperature_status();
{% end %}

     }, 1000);
});


function rename_device(fan_index)
{
    var default_name = "Fan #"+ (parseInt(fan_index)+1)
    let name = prompt("New name for this device (A-Z, 0-9, -, _ and spaces allowed)", default_name);
    var hitCancel = !(name != "" && name !== null);

    if (hitCancel)
    {
        return;
    }

    name = encodeURIComponent(name)
    var url = '/api/v0/alias/'+ fan_index +'/set?value='+name;

    console.log("New name: "+ name);
    console.log("Sending request to: "+ url);
    var jqxhr = $.get( url, function() {
    })
      .done(function(e) {
        gui_update_fan_aliases();
      })
      .fail(function(e) {
        console.log(e);
        alert("Failed to update fan name. Please check console for detailed error.");
      });

}

{% if board['has_profiles'] %}

$(function() {
    $("#set-fan-profile").on("click", function() {
        const profile_name = $('#available-fan-profiles').find(":selected").val();

        if (profile_name != undefined && profile_name != "")
        {
            gui_set_fan_profile(profile_name);
        }
        else
        {
            console.log("Fan profile list is empty...");
        }

    });
});

function ui_list_available_profiles()
{
    $('#available-fan-profiles').text("");

    var url = '/api/v0/profiles/list';
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const fan_profiles = Object.values(e['data']);

        if (fan_profiles.length > 0)
        {
            fan_profiles.forEach(function (data) {
                html = '<option value="'+ data['name'] +'">'+ data['name'] +'</option>';
                $('#available-fan-profiles').append(html);
            });
        }
        else
        {
            html = '<option value="">No profiles. Maybe create one?</option>';
            $('#available-fan-profiles').append(html);
        }

      })
      .fail(function(e) {
            html = '<option >Failed to load profiles...</option>';
            $('#available-fan-profiles').append(html);
      });
}


function gui_set_fan_profile(name)
{
    var url = '/api/v0/profiles/set?name='+ name;
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const status = e['status'];
        if (status == 'ok')
        {
            console.log("Profile "+ name +" selected.");
        }
        else
        {
            alert('Failed to load fan profile "'+ name +'". Error: "'+ e['message'] +'"');
        }
      });
}
{% end %}

function gui_update_fan_status()
{
    var url = '/api/v0/fan/status';
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const rpm = Object.values(e['data']);

        rpm.forEach(function (value, index) {
            $("#fan-"+ index +"-rpm").text(value);
            $('.rpm-suffix').show();
        });

      })
      .fail(function(e) {
        $('.rpm-suffix').hide();
        {% for i in range(board['fan_count']) %}
        $("#fan-{{i}}-rpm").text('_COM_ERR_');{% end %}
      });
}

function gui_update_temperature_status()
{
    var url = '/api/v0/sensor/temperature/all/get';
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const temperature = Object.values(e['data']);

        temperature.forEach(function (value, index) {
            if (value < 0)
            {
                value = 'Disconnected';
                $("#sensor-"+ index +"-unit").hide();
            }
            else
            {
                $("#sensor-"+ index +"-unit").show();
            }
            $("#sensor-"+ index +"-temperature").text(value);
        });

      })
      .fail(function(e) {
        {% for i in range(board['sensor_count']) %}
        $("#sensor-{{i}}-temperature").text('_COM_ERR_');{% end %}

      });
}

function update_fan(fan, value)
{
    var control_via_rpm = $("#control_via_rpm").is(":checked")
    if(control_via_rpm)
    {
        value = parseInt(value, 10);
        var url = '/api/v0/fan/'+ fan + '/rpm?value='+value;
    }
    else
    {
        value = parseInt((value), 10);
        var url = '/api/v0/fan/'+ fan + '/set?value='+value;
    }

    console.log("Sending request to: "+ url);
    var jqxhr = $.get( url, function() {
    })
      .done(function(e) {
        console.log(e);
      })
      .fail(function(e) {
        console.log(e);
      });

}


function gui_update_fan_aliases()
{
    var url = '/api/v0/alias/all/get';
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const rpm = Object.values(e['data']);

        rpm.forEach(function (value, index) {
            $("#fan-"+ index +"-name").text(value);
        });

      })
      .fail(function(e) {
        {% for i in range(board['fan_count']) %}
        $("#fan_{{i}}_name").text('ERR');{% end %}
      });
}

function radio_control_via_rpm_handler()
{
    var control_via_rpm = $("#control_via_rpm").is(":checked")

    if(control_via_rpm === true)
    {
        $('label[for="control_via_rpm"]').text('Control in RPM (Revolutions Per Minute)');
        $("#fan_value").attr({
           "min" : 500,
           "max" : 3000,
           "step": 50
        });
        $("#fan_value").val(1000);
    }
    else
    {
        $('label[for="control_via_rpm"]').text('Control in PWM percentage');
        $("#fan_value").attr({
           "min" : 0,
           "max" : 100,
           "step": 5
        });
        $("#fan_value").val(50);
    }
    update_value_slider();
}


function update_value_slider()
{
    var fan_value = $("#fan_value").val();
    var use_rpm = $("#control_via_rpm").is(":checked")
    var label;

    if(use_rpm === true)
    {
        if (fan_value <= 480)
        {
            label = 'Target RPM: OFF';
        }
        else
        {
            label = 'Target RPM: '+ fan_value;
        }
    }
    else
    {
        label = 'Fan PWM: '+ fan_value +'%';
    }

    $('label[for="fan_value"]').text(label);
}

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
