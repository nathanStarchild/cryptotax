<script>
//We can use this file to add js to all pages with the ability to use Django template things in the file

//a handy little function to use in if statements
$.fn.exists = function () {
    return this.length !== 0;
}

$(document).ready(function() {
    //handle form errors
    {% if form %}
        let msg = "{{message}}";
        {% for error in form.non_field_errors %}
            msg += "{{error|safe}} ";
        {% endfor %}
        {% for field in form %}
            {% if field.errors %}
                $("#{{field.id_for_label}}").addClass("is-invalid");
                {% for error in field.errors %}
                    msg += "{{error|safe}} ";
                {% endfor %}
            {% endif %}
        {% endfor %}
        if (msg){
            $("#messageContent").text(msg);
            $("#message").slideDown();
        }
    {% endif %}
});


async function postData(url, data){
    const response = await fetch(url, {
        method: 'POST', 
        headers: {
        // 'Content-Type': 'application/json'
        'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: data // body data type must match "Content-Type" header
    });
    return response.json(); // parses JSON response into native JavaScript objects
}

async function postForm($form){
    // console.log($form.serialize())
    console.log($form)
    return postData($form.attr('action'), $form.serialize());
}

async function postFormWithFile($form){
    let data = new FormData($form[0])
    const response = await fetch($form.attr('action'), {
        method: "POST",
        body: data
    });
    return response.json();

}

function singleDatePicker(){
    let dateFormat = "dd/mm/yy"
    $("#id_date")
        .datepicker({
            // defaultDate: 0,,
            changeMonth: true,
            changeYear: true,
            numberOfMonths: 1,
            dateFormat: dateFormat,
        }) 
}   

function fromDateToDatePickers(){
    let dateFormat = "dd/mm/yy"
    $("#id_fromDate")
        .datepicker({
            // defaultDate: 0,,
            changeMonth: true,
            changeYear: true,
            numberOfMonths: 1,
            dateFormat: dateFormat,
        })
        .on( "change", function() {
            to.datepicker( "option", "minDate", getDate( this ) );
        }); 

    to = $("#id_toDate")
        .datepicker({
            // defaultDate: 0,,
            changeMonth: true,
            changeYear: true,
            numberOfMonths: 1,
            dateFormat: dateFormat,
        });     
        
    function getDate( element ) {
        var date;
        try {
            date = $.datepicker.parseDate( dateFormat, element.value );
        } catch( error ) {
            date = null;
        }
        return date;
    }    
}

function toLocal(date) {
    var local = new Date(date);
    local.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return local.toJSON();
}
  
function toJSONLocal(date) {
    var local = new Date(date);
    local.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return local.toJSON().replace("T", " ").slice(0, 19);
}

</script>