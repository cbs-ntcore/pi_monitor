var monitors = [];

var recording_state_poll_interval = 10000;
var idle_state_poll_interval = 3000;

var stream_interval = 1000;
var stream_timer = null;

var recording = null;


class Monitor {
	constructor(ip, port) {
		this.ip = ip;
		this.port = port;
		this.is_idle = false;
		this.endpoint = "/monitor" + ip.split(".")[3] + "/";

		// add html elements from monitor_template
		let elements = document.getElementById("monitor_template").content.cloneNode(true);
		// setup elements
		elements.querySelector(".monitor_div").id = ip + "_div";
		elements.querySelector(".monitor_title").textContent = "Monitor IP: " + ip;
		// TODO setup other elements
		document.getElementById("monitors_div").appendChild(elements);
		this.element = document.getElementById(ip + "_div");

		// TODO setup and enable state timer
		this.state_timer = null;
		this.update_state();
	}

	update_image(callback) {
		call_method("current_frame", undefined, undefined, (image) => {
			this.element.querySelector(".video_frame").src = "data:image/jpeg;base64, " + image;
			if (callback !== undefined) callback(image);
		}, this.endpoint);
	}

	start_recording() {
		call_method("start_recording", undefined, undefined, undefined, this.endpoint);
	}

	stop_recording() {
		call_method("stop_recording", undefined, undefined, undefined, this.endpoint);
	}

	update_state() {
		call_method("get_state", undefined, undefined, (state) => {
			this.state = state;
			// FIXME this is an ugly way to check if any monitors are recording
			update_recording_state();
			// state = {recording: bool, converting: bool, disk_space: int}
			// update disk space
			let el = this.element.querySelector(".disk_space");
			if (state.disk_space < 500000000) {
				el.style.color = "#cc0000";
			} else {
				el.style.color = "";
			};
			let suffix = "";
			for (let unit of ["K", "M", "G", "T"]) {
				if (state.disk_space > 1000) {
					state.disk_space /= 1000;
					suffix = unit;
				} else {
					break;
				};
			};
			el.innerHTML = state.disk_space.toFixed(2) + suffix;

			// state string (recording/converting/idle)
			let state_string = ""
			el = this.element.querySelector(".state");
			let rbtn = this.element.querySelector('.record_btn');
			if (state.recording) {
				state_string = "Recording";
				this.is_idle = false;
				el.style.color = "#00cc00";
				// set record button to stop
				rbtn.classList.add("onair");
				rbtn.innerHTML = "Stop Recording";
			} else {
				rbtn.classList.remove("onair");
				rbtn.innerHTML = "Start Recording";
			};
			if (state.converting) {
				if (state_string.length) state_string += ",";
				state_string += "Converting";
				this.is_idle = false;
				el.style.color = "#cc0000";
			};
			if (state_string.length == 0) {
				state_string = "Idle";
				this.is_idle = true;
				el.style.color = "";
			};
			el.textContent = state_string;
			let interval = state.recording ? recording_state_poll_interval : idle_state_poll_interval;
			if (this.state_timer !== null) {
				clearTimeout(this.state_timer);
				this.state_timer = null;
			};
			this.state_timer = setTimeout(() => {this.update_state();}, interval);
		}, this.endpoint);
	}
};

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
	//console.log({method: method, args: args, kwargs: kwargs, callback: callback, endpoint: endpoint});
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


update_all_images = function () {
	for (let monitor of monitors) {
		monitor.update_image();
	};
};


toggle_streaming = function () {
	let el = document.getElementById("stream_btn");
	if (stream_timer !== null) {
		clearInterval(stream_timer);
		el.innerHTML = "Start Streaming";
    } else {
		stream_timer = setInterval(update_all_images, stream_interval);
		el.innerHTML = "Stop Streaming";
    };
};


update_recording_state = function (new_state) {
	if (new_state === undefined) {
		recording = false;
		for (let monitor of monitors) {
			if (monitor.state === undefined) {
				// unknown monitor state
				continue;
			};
			if (monitor.state.recording) {
				// since one thing is recording, assume global recording state
				recording = true;
				break;
			};
		};
	} else {
		recording = new_state;
	};
	let el = document.getElementById("record_btn");
	if (recording) {
		el.classList.add("onair");
		el.innerHTML = "Stop Recording";
	} else {
		el.classList.remove("onair");
		el.innerHTML = "Start Recording";
	};
};


toggle_recording = function () {
	if (recording) {
		// stop recording
		for (let monitor of monitors) monitor.stop_recording();
	} else {
		// start recording
		for (let monitor of monitors) monitor.start_recording();
	};
	for (let monitor of monitors) monitor.update_state();
	update_recording_state(!recording);
};


setup_monitors = function (monitor_info) {
	// monitors = [(ip, port), ...]
	// for each monitor
	for (monitor_info of monitor_info) {
		ip = monitor_info[0];
		port = monitor_info[1];
		monitors.push(new Monitor(ip, port));
	};
};


window.onload = function () {
	// get monitor info [(ip, port), ...]
	call_method("get_monitors", undefined, undefined, setup_monitors, "/controller/");
};
