// When page is loaded
$(function() {
    gui_update_fan_profiles();

    $("#fan_value").on("input change", function() {
        update_value_slider();
    } );

    $("#control_via_rpm").on("input change", function() {
        radio_control_via_rpm_handler();
    });

    $("#unlock_range").on("input change", function() {
        radio_extend_range_handler()
    });

    $("#modal-ranges").on("input change", function() {
        const fan_id = $(event.target).data('fan-id');
        const val = $(event.target).val();
        const control_option = $('input[name="fan-control-option"]:checked').val();
        gui_new_profile_update_label(fan_id, val, control_option);
    });

    $("#modal-ctl-select").on("input change", function() {
        gui_new_profile_handle_control_switch();
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


    // Periodic fan RPM update
    const interval = setInterval(function() {
       gui_update_fan_status();
     }, 1000);
});


function gui_new_profile_adjust_range()
{

}

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
    const fan1 = $("#new-fp-fan-1").val();
    const fan2 = $("#new-fp-fan-2").val();
    const fan3 = $("#new-fp-fan-3").val();
    const fan4 = $("#new-fp-fan-4").val();
    const fan5 = $("#new-fp-fan-5").val();
    const fan6 = $("#new-fp-fan-6").val();
    const fan7 = $("#new-fp-fan-7").val();
    const fan8 = $("#new-fp-fan-8").val();
    const fan9 = $("#new-fp-fan-9").val();
    const fan10 = $("#new-fp-fan-10").val();

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
            gui_update_fan_profiles();
        }
        else
        {
            alert('Failed to create new fan profile "'+ name +'". Error: "'+ e['message'] +'"');
        }

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

function gui_update_fan_profiles()
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

function gui_update_fan_status()
{
    var url = '/api/v0/fan/status';
    var jqxhr = $.getJSON(url, function() {
    })
      .done(function(e) {
        const rpm = Object.values(e['data']);

        rpm.forEach(function (value, index) {
            $("#fan-"+ index +"-rpm").text(value);
        });

      })
      .fail(function(e) {
        $("#fan_0_rpm").text('ERR RPM');
        $("#fan_1_rpm").text('ERR RPM');
        $("#fan_2_rpm").text('ERR RPM');
        $("#fan_3_rpm").text('ERR RPM');
        $("#fan_4_rpm").text('ERR RPM');
        $("#fan_5_rpm").text('ERR RPM');
        $("#fan_6_rpm").text('ERR RPM');
        $("#fan_7_rpm").text('ERR RPM');
        $("#fan_8_rpm").text('ERR RPM');
        $("#fan_9_rpm").text('ERR RPM');
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
    var extended_range = $("#unlock_range").is(":checked");
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

