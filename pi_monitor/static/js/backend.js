var config_editor = null;
var state_poll_timer = null;


get_config = function (cb, endpoint) {
	if (endpoint == undefined) endpoint = "/camera/";
	cmd = {
		method: "get_config",
	};
	fetch(endpoint, {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) console.log({response_error: response});
		response.json().then((data) => {
			if (data.type == "error") {
				console.log({data_error: data.result});
			} else {
				config_editor.set(data.result);
				document.getElementById("config").style.backgroundColor = "";
				if (cb !== undefined) cb();
			};
		});
	});
};


set_config = function (endpoint) {
	if (endpoint == undefined) endpoint = "/camera/";
	cfg = config_editor.get();
	console.log({set_config: cfg});
	cmd = {
		method: "set_config",
		args: [cfg, ],
	};
	fetch(endpoint, {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) {
			console.log({response_error: response});
		} else {
			document.getElementById("config").style.backgroundColor = "";
		};
	});

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


get_image = function () {
	cmd = {method: "current_frame"};
	fetch("/camera/", {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) console.log({response_error: response});
		response.json().then((data) => {
			if (data.type == "error") {
				console.log({data_error: data.error});
			} else {
				new_image(data.result);
			};
		});
	});
};


new_image = function (image) {
	document.getElementById("video_frame").src = "data:image/jpeg;base64, " + image;
};


/*
get_state = function () {
	// TODO add check for state id
	cmd = {
		method: "get_state",
	};
	fetch("/backend/", {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) console.log({response_error: response});
		response.json().then((data) => {
			if (data.type == "error") {
				console.log({data_error: data.error});
			} else {
				new_state(data.result);
			};
		});
	});
};


new_state = function (state) {
	document.getElementById("ticks_label").innerHTML = "" + state.ticks;
	document.getElementById("rpm_label").innerHTML = "" + state.motor.rpm.toFixed(2);
	document.getElementById("radius_label").innerHTML = "" + state.spool.radius.toFixed(4);
	document.getElementById("err_label").innerHTML = "" + state.pid.err.toFixed(4);
	document.getElementById("found_label").innerHTML = "" + state.tracker.found;
	if (state.tracker.found) {
		x = "" + state.tracker.x.toFixed(4);
		y = "" + state.tracker.y.toFixed(4);
		angle = "" + state.tracker.angle.toFixed(4);
	} else {
		x = "?";
		y = "?";
		angle = "?";
	};
	document.getElementById("x_label").innerHTML = x;
	document.getElementById("y_label").innerHTML = y;
	document.getElementById("angle_label").innerHTML = angle;
	if (state.frame_b64 !== undefined)
		document.getElementById("video_frame").src = "data:image/jpeg;base64, " + state.frame_b64;
};


grab_background = function () {
	cmd = {
		method: "grab_background",
	};
	fetch("/backend/", {
		method: "POST", body: JSON.stringify(cmd),
		headers: {"Content-type": "application/json"},
	}).then((response) => {
		if (response.status !== 200) console.log({response_error: response});
		response.json().then((data) => {
			if (data.type == "error") console.log({data_error: data.error});
		});
	});
};

slider_changed = function () {
	cfg = config_editor.get();
	cfg.control.rpm = Number(this.value);
	config_editor.update(cfg);
	set_config();
};
*/

window.onload = function () {
	config_editor = new JSONEditor(
		document.getElementById("config"), {onChange: config_modified});
	// fetch config
	get_config();
	// repeatedly fetch image
	image_poll_timer = setInterval(get_image, 300);
};
