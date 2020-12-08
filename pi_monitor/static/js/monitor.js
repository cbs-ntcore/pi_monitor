var config_editor = null;
var image_poll_timer = null;
var state_poll_timer = null;
var recording_state_poll_interval = 60000;
var idle_state_poll_interval = 1000;
var state_poll_interval = recording_state_poll_interval;


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
			el.classList.add("onair");
			el.innerHTML = "Stop Record";
			state_poll_interval = recording_state_poll_interval;
		} else {
			el.classList.remove("onair");
			el.innerHTML = "Start Record";
			state_poll_interval = idle_state_poll_interval;
		};
		if (cb !== undefined) cb(result);
		get_state();
	};
	call_method("get_config", undefined, undefined, callback, "/camera/");
};


set_config = function (save) {
	if (save === undefined) save = false;
	cfg = config_editor.get();
	call_method("set_config", [cfg, ], {save: save}, function (result) {
		document.getElementById("config").classList.remove("hot");
		get_state();
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
	if (image_poll_timer !== undefined) {
		clearInterval(image_poll_timer);
		image_poll_timer = undefined;
	};
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


list_filenames = function(filenames, directory) {
	ul = document.getElementById("filename_list");

	// remove all current filenames
	while (ul.firstChild) {
		ul.removeChild(ul.firstChild);
	};

	// sort filenames
	filenames.sort();
	for (let filename of filenames) {
		// color code by extension
		pi = filename.lastIndexOf('.')
		if (pi == -1) {
			ext = "";
		} else {
			ext = filename.substr(pi + 1);
		};
		li = document.createElement("li");
		link = document.createElement("a");
		// link to download file
		link.href = "/camera/" + filename;
		link.text = filename;
		li.appendChild(link)
		//li.appendChild(document.createTextNode(filename));
		if (ext == "h264") {
			// add convert buttons extension for h264 files
			btn = document.createElement("button");
			btn.textContent = "Convert";
			btn.onclick = function () {
				call_method(
					"convert_video", [directory + "/" + filename],
					undefined, undefined, "/filesystem/");
			};
			li.appendChild(btn);
		};
		// add download buttons for all files
		btn = document.createElement("button");
		btn.textContent = "Download";
		//li.appendChild(btn);
		// add delete files (with confirm) for all files
		if (document.getElementById("can_remove").checked) {
			btn = document.createElement("button");
			btn.textContent = "Remove";
			btn.onclick = function () {
				call_method(
					"delete_file", [directory + "/" + filename], undefined,
					get_state, "/filesystem/");
			};
			btn.classList.add("hot");
			li.appendChild(btn);
		};
		ul.appendChild(li);
	};
};


get_state = function () {
	// reset state timer
	if (state_poll_interval != 0) {
		if (state_poll_timer !== undefined) {
			clearTimeout(state_poll_timer);
		};
		state_poll_timer = setTimeout(get_state, state_poll_interval);
	};

	cfg = config_editor.get();  // TODO what if config editor is open?
	directory = cfg['video_directory'];

	// space left on disk
	call_method("get_disk_space", [directory, ], undefined, function (result) {
		el = document.getElementById("disk_space");
		el.innerHTML = result;
		// color based on amount left
		zeros = "000"
		for (unit of ["K", "M", "G", "T"]) {
			result = result.replace(unit, zeros);
			zeros += "000";
		}
		bytes = Number(result) / 1000000;  // MB
		if (bytes < 500) {
			el.style.color = "#ff0000";
		};
	}, "/filesystem/");

	// videos
	call_method("get_filenames", [directory, ], undefined, function (result) {
		list_filenames(result, directory);
	}, "/filesystem/");

	call_method("is_conversion_running", undefined, undefined, function (result) {
		el = document.getElementById("conversion_indicator");
		if (result) {
			el.classList.add("enabled");
			el.innerHTML = "Conversion Active";
			el.style.color = "#ff0000";
		} else {
			el.classList.remove("enabled");
			el.innerHTML = "Conversion Idle";
			el.style.color = "";
		};
	}, "/filesystem/");
};


shutdown_system = function () {
	call_method("shutdown", undefined, undefined, undefined, "/system/");
}


restart_service = function () {
	call_method("restart_service", undefined, undefined, undefined, "/system/");
	setTimeout(function() {location.reload()}, 1000);
}


window.onload = function () {
	config_editor = new JSONEditor(
		document.getElementById("config"), {onChange: config_modified});
	// fetch config
	get_config();
	// repeatedly fetch image
	stop_streaming();
};
