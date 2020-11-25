var config_editor = null;
var image_poll_timer = null;
var state_poll_timer = null;


report_error = function (msg, data) {
	console.log({[msg]: data});
	ds = JSON.stringify(data);
	s = msg + ": " + ds;
	if (s.length > 80) {
		s = s.substring(0, 75) + " ...";
	};
	ul = document.getElementById("error_list");
	li = document.createElement("li");
	li.appendChild(document.createTextNode(s));
	ul.appendChild(li);
};


call_method = function (method, args, kwargs, callback, endpoint) {
	if (endpoint === undefined) endpoint = "/camera/";
	cmd = {method: method};
	if (args !== undefined) cmd.args = args;
	if (kwargs !== undefined) cmd.kwargs = kwargs;
	fetch(endpoint, {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		//if (response.status !== 200) console.log({response_error: response});
		if (response.status !== 200) report_error("response_error", response);
		response.json().then((data) => {
			if (data.type == "error") {
				// TODO pipe errors to page
				//console.log({data_error: data.error});
				report_error("data_error", data.error);
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
		document.getElementById("config").classList.remove("hot");
		el = document.getElementById("record_btn");
		if (result['record']) {
			el.classList.add("hot");
			el.innerHTML = "Stop Record";
		} else {
			el.classList.remove("hot");
			el.innerHTML = "Start Record";
		};
		if (cb !== undefined) cb(result);
		get_state();  // TODO attach to timer
	};
	call_method("get_config", undefined, undefined, callback, "/camera/");
};


set_config = function (save) {
	if (save === undefined) save = false;
	cfg = config_editor.get();
	call_method("set_config", [cfg, ], {save: save}, function (result) {
		document.getElementById("config").classList.remove("hot");
		get_state();  // TODO attach to timer
	}, "/camera/");
};


config_modified = function () {
    console.log({config_modified: config_editor});
	document.getElementById("config").classList.add("hot");
};


toggle_config = function () {
    el = document.getElementById("config_editor");
	if (el.hidden) {
		get_config(function() {document.getElementById("config_editor").hidden = false;});
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
	el = document.getElementById("stream_btn");
	el.classList.remove("hot");
	el.innerHTML = "Start Stream";
};


start_streaming = function (interval) {
	if (image_poll_timer !== undefined) stop_streaming();
	if (interval === undefined) interval = 1000;
	image_poll_timer = setInterval(get_image, interval);
	el = document.getElementById("stream_btn");
	el.classList.add("hot");
	el.innerHTML = "Stop  Stream";
};


toggle_streaming = function () {
	if (image_poll_timer === undefined) {
		cfg = config_editor.get();
		start_streaming(cfg['stream_period']);
	} else {
		stop_streaming();
	};
};


toggle_recording = function () {
	cfg = config_editor.get();  // TODO what if config editor is open?
	method = cfg['record'] ? "stop_recording" : "start_recording";
	call_method(method, undefined, undefined, function (result) {
		get_config();  // update config from backend
	}, "/camera/");
};


get_state = function () {
	cfg = config_editor.get();  // TODO what if config editor is open?
	directory = cfg['video_directory'];

	// space left on disk
	call_method("get_disk_space", [directory, ], undefined, function (result) {
		el = document.getElementById("disk_space");
		el.innerHTML = result;
		// TODO color based on amount left
	}, "/filesystem/");

	// videos
	call_method("get_filenames", [directory, ], undefined, function (result) {
		// list of filenames all in directory
	}, "/filesystem/");

	// TODO also list conversion running?
	call_method("is_conversion_running", undefined, undefined, function (result) {
		el = document.getElementById("conversion_indicator");
		if (result) {
			el.classList.add("enabled");
			el.innerHTML = "Conversion Active";
		} else {
			el.classList.remove("enabled");
			el.innerHTML = "Conversion Idle";
		};
	}, "/filesystem/");
};


window.onload = function () {
	config_editor = new JSONEditor(
		document.getElementById("config"), {onChange: config_modified});
	// fetch config
	get_config();
	// repeatedly fetch image
	start_streaming();
};
