$ = jQuery;

$(document).ready(function(){
	main_init();
});


function main_init(){
	init_add_buttons();
}


function init_add_buttons(){
	$(".btn.test-api").click(function(e){
		e.preventDefault();
		
		var parent = $(this).parents("tr");
		var method = parent.find(".api-method").text()
		var dest = parent.find(".response pre");
		dest.html("Loading...");
		dest.removeClass("fail success");
		var ajx = {
			type: method,
			url: parent.find(".api-endpoint").text(),
			dataType:"json",
			success: function(response){
				dest.html(pretty(JSON.stringify(response)));
				dest.addClass("success");
			},
			 error: function (request, status, error) {
				dest.html("An error appeared:" + request.responseText);
				dest.addClass("fail");
			}
		};
		if(method === "POST"){
			ajx.data = parent.find(".api-data textarea").val();
		}
		$.ajax(ajx);

	}); 
}

function pretty(s){
	s = s.replaceAll("{",'<span class="pretty-accolade-open">{</span>');
	s = s.replaceAll("}",'<span class="pretty-accolade-close">}</span>');
	s = s.replaceAll('","','"<span class="pretty-comma">,</span>"');
	return s;
}
