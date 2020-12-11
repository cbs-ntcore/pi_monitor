var monitors = [];

var recording_state_poll_interval = 10000;
var idle_state_poll_interval = 3000;

var file_info_poll_interval = 5000;
var file_info_timer = null;

var stream_interval = 1000;
var stream_timer = null;

var recording = null;
var video_directory = null;


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
		document.getElementById("monitors_div").appendChild(elements);
		this.element = document.getElementById(ip + "_div");
		this.element.querySelector(".record_btn").onclick = () => {
			this.toggle_recording();
			this.update_state();
		};
		call_method("link_url", undefined, undefined, (link) => {
			this.element.querySelector(".frame_link").href = link;
		}, this.endpoint);

		// setup and enable state timer
		this.state = null;
		this.state_timer = null;
		this.update_state();

		this.file_info = null;
		this.file_info_timer = null;
		this.update_file_info();
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

	toggle_recording() {
		call_method("toggle_recording", undefined, undefined, undefined, this.endpoint);
	}

	update_file_info() {
		call_method("get_file_info", undefined, undefined, (file_info) => {
			this.file_info = file_info;
			// count open files
			// organize by basename
			let n_open = 0;
			let by_ext = {};
			for (let info of file_info) {
				if (info.open) n_open += 1;
				let ext = info.name.split(".")[1]
				if (!(ext in by_ext)) by_ext[ext] = 0;
				by_ext[ext] += 1;
			};
			let file_info_string = String(n_open) + " Open, ";
			for (let ext in by_ext) {
				let n = by_ext[ext]
				file_info_string += String(n) + " " + ext + ", ";
			};
			this.element.querySelector(".file_info").textContent = file_info_string.substring(
				0, file_info_string.length - 2);

			if (this.file_info_timer !== null) {
				clearTimeout(this.file_info_timer);
				this.file_info_timer = null;
			};
			this.file_info_timer = setTimeout(
				() => {this.update_file_info();}, file_info_poll_interval);
		}, this.endpoint);
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
		el.classList.remove("hot");
    } else {
		stream_timer = setInterval(update_all_images, stream_interval);
		el.innerHTML = "Stop Streaming";
		el.classList.add("hot");
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


convert_all_files = function () {
	let check_conversion = function () {
		call_method("is_converting", undefined, undefined, function (result ) {
			let el = document.getElementById("convert_btn");
			if (result) {  // still converting
				// call this again 1 second later
				setTimeout(check_conversion, 1000);
				el.classList.add("hot");
			} else {
				// clean up after conversion
				el.innerHTML = "Convert";
				el.classList.remove("hot");
			};
		}, "/controller/");
	};
	call_method(
		"convert_all_files", undefined, undefined, check_conversion, "/controller/");
};


transfer_all_files = function () {
	call_method("transfer_files", [video_directory, ], undefined, () => {
		// wait for is_transferring to finish
		check_transfer = function () {
			call_method("is_transferring", undefined, undefined, (is_transferring) => {
				let el = document.getElementById("transfer_btn");
				if (is_transferring) {
					// still transferring
					setTimeout(check_transfer, 1000);
				} else {
					// finished
					el.classList.remove("hot");
				};
			}, "/controller/");
		};
		el.classList.add("hot");
		setTimeout(check_transfer, 1000);
	}, "/controller/");
}


get_file_info = function () {
	call_method("static_directory", [video_directory, ], undefined, undefined, "/filesystem/");
	// recursive file get
	call_method("get_file_info", [video_directory, true], undefined, (file_info) => {
		let ul = document.getElementById("filename_list");
		// remove all current filenames
		while (ul.firstChild) ul.removeChild(ul.firstChild);
		// sort file info by name
		file_info.sort((a, b) => {
			if (a.name > b.name) return 1; return (a.name < b.name) ? -1 : 0;});
		for (let info of file_info) {
			// color code by extension?
			let li = document.createElement("li");
			let link = document.createElement("a");
			link.href = "/filesystem/" + info.name;
			link.text = info.name;
			li.append(link);
			if (document.getElementById("can_remove").checked) {
				let btn = document.createElement("button");
				btn.textContent = "Remove";
				btn.onclick = () => {
					call_method(
						"delete_file", [video_directory + "/" + info.name], undefined,
						get_file_info, "/filesystem/");
				};
				btn.classList.add("hot");
				li.appendChild(btn);
			};
			ul.append(li);
		};
		// setup to call this again
		if (file_info_timer !== null) {
			clearTimeout(file_info_timer);
			file_info_timer = null;
		};
		file_info_timer = setTimeout(get_file_info, file_info_poll_interval);
	}, "/filesystem/");
}


window.onload = function () {
	let el = document.getElementById("directory_input");
	video_directory = el.value;
	// TODO get directory from backend [loaded from default config]
	el.onkeydown = (key) => {
		if (key.keyCode == 13) {
			el.classList.remove("hot");
			video_directory = el.value;
			get_file_info();
		} else {
			el.classList.add("hot");
		};
	};

	// get monitor info [(ip, port), ...]
	call_method("get_monitors", undefined, undefined, setup_monitors, "/controller/");
	get_file_info();
};
