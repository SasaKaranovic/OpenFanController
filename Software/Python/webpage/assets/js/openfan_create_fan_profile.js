$(function() {
    $("#submit-new-profile").on("click", function(e) {
        if ($('#new-fp-name').val() == undefined || $('#new-fp-name').val() == "")
        {
            alert("Please set profile name!");
        }
        else
        {
            gui_submit_new_profile();
        }
    } );

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

    $("#delete-fan-profile").on("click", function() {
        const profile_name = $('#available-fan-profiles').find(":selected").val();

        if (profile_name != undefined || profile_name != "")
        {
            gui_delete_fan_profile(profile_name);
        }
        else
        {
            console.log("Fan profile list is empty...");
        }

    });

    $("#ranges").on("input change", function() {
        const fan_id = $(event.target).data('fan-id');
        const val = $(event.target).val();
        const control_option = $('input[name="fan-control-option"]:checked').val();
        gui_new_profile_update_label(fan_id, val, control_option);
    });

    $("#modal-ctl-select").on("input change", function() {
        gui_new_profile_handle_control_switch();
    });

    ui_list_available_profiles();
});

// Fan profiles
function gui_new_profile_update_label(fan_id, value, ctlType)
{
    let suffix = '% PWM';

    if (ctlType == 'rpm')
    {
        suffix = ' RPM';
    }

    $("#label-range-fan-" + fan_id).text(value + suffix);
}

function gui_new_profile_update_range(fan_id, min, max, step, val)
{
        $("#new-fp-fan-"+ fan_id).attr({
           "min" : min,
           "max" : max,
           "step": step,
           "value" : val
        });

        $("#new-fp-fan-"+ fan_id).val(val);
}

function gui_new_profile_handle_control_switch()
{
    const control_option = $('input[name="fan-control-option"]:checked').val();
    let min = 0;
    let max = 3000;
    let step = 5;
    let current_val = 1000;

    if (control_option != 'rpm')
    {
        min = 0;
        max = 100;
        step = 5;
        current_val = 50;
    }

    for (let i=1; i<=10; i++)
    {
        gui_new_profile_update_label(i, current_val, control_option);
        gui_new_profile_update_range(i, min, max, step, current_val);
    }
}

function gui_submit_new_profile()
{
    {% for i in range(board['fan_count']) %}
    const fan{{i+1}} = $("#new-fp-fan-{{i+1}}").val();
    {% end %}

    const fan_str = fan1 +'%3B'+ fan2 +'%3B'+ fan3 +'%3B'+ fan4 +'%3B'+ fan5 +'%3B'+ fan6 +'%3B'+ fan7 +'%3B'+ fan8 +'%3B'+ fan9 +'%3B'+ fan10;
    const name = $('#new-fp-name').val();
    const control_option = $('input[name="fan-control-option"]:checked').val();

    var url = '/api/v0/profiles/add?name='+ name + '&type='+ control_option +'&values='+fan_str;
    var jqxhr = $.post(url, function() {
    })
      .done(function(e) {
        const status = e['status'];
        if (status == 'ok')
        {
            console.log("Profile "+ name +" created.");
            ui_list_available_profiles();
        }
        else
        {
            alert('Failed to create new fan profile "'+ name +'". Error: "'+ e['message'] +'"');
        }
      });
}

function gui_delete_fan_profile(name)
{
    var url = '/api/v0/profiles/remove?name='+ name;
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const status = e['status'];
        if (status == 'ok')
        {
            $("#available-fan-profiles option[value='"+ name+"']").remove();
        }
        else
        {
            alert('Failed to load fan profile "'+ name +'". Error: "'+ e['message'] +'"');
        }
      });
}

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
