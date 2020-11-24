var config_editor = null;
var image_poll_timer = null;


call_method = function (method, args, kwargs, callback, endpoint) {
	if (endpoint === undefined) endpoint = "/camera/";
	cmd = {method: method};
	if (args !== undefined) cmd.args = args;
	if (kwargs !== undefined) cmd.kwargs = kwargs;
	fetch(endpoint, {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) console.log({response_error: response});
		response.json().then((data) => {
			if (data.type == "error") {
				console.log({data_error: data.error});
			} else {
				if (callback !== undefined)
					callback(data.result);
			};
		});
	});
};


get_config = function (cb) {
	callback = function (result) {
		config_editor.set(result);
		document.getElementById("config").style.backgroundColor = "";
		if (cb !== undefined) cb(result);
	};
	call_method("get_config", undefined, undefined, callback, "/camera/");
};


set_config = function () {
	cfg = config_editor.get();
	call_method("set_config", [cfg, ], undefined, function (result) {
		document.getElementById("config").style.backgroundColor = "";
	}, "/camera/");
};


config_modified = function () {
    console.log({config_modified: config_editor});
	document.getElementById("config").style.backgroundColor = "#ffeeee";
};


toggle_config = function () {
    el = document.getElementById("config_editor");
	if (el.hidden) {
		get_config(function() {el.hidden = false;});
	} else {
		el.hidden = true;
	};
};


new_image = function (image) {
	document.getElementById("video_frame").src = "data:image/jpeg;base64, " + image;
};


get_image = function () {
	call_method("current_frame", undefined, undefined, new_image, "/camera/");
};


stop_streaming = function () {
	if (image_poll_timer === undefined) return;
	clearInterval(image_poll_timer);
	image_poll_timer = undefined;
};


start_streaming = function (interval) {
	if (image_poll_timer !== undefined) stop_streaming();
	if (interval === undefined) interval = 1000;
	image_poll_timer = setInterval(get_image, interval);
};


window.onload = function () {
	config_editor = new JSONEditor(
		document.getElementById("config"), {onChange: config_modified});
	// fetch config
	get_config();
	// repeatedly fetch image
	start_streaming();
};
