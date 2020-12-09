var monitors = [];


class Monitor {
	constructor(ip, port) {
		this.ip = ip;
		this.port = port;
		this.endpoint = "monitor" + ip.split(".")[3]
		// add html elements from monitor_template
		let elements = document.getElementById("monitor_template").content.cloneNode(true);
		// setup elements
		elements.querySelector(".monitor_div").id = ip + "_div";
		elements.querySelector(".monitor_title").textContent = "Monitor IP: " + ip;
		// TODO setup other elements
		document.getElementById("monitors_div").appendChild(elements);
		// TODO setup and enable state timer
		this.element = document.getElementById(ip + "_div");
	}

	update_image() {
		call_method("current_frame", undefined, undefined, (image) => {
			this.element.querySelector('.video_frame').src = "data:image/jpeg;base64, " + image;
		}, this.endpoint);
	}
}

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


setup_monitors = function (monitor_info) {
	// monitors = [(ip, port), ...]
	// for each monitor
	for (monitor_info of monitor_info) {
		ip = monitor_info[0];
		port = monitor_info[1];
		monitors.push(new Monitor(ip, port));
	};
}

window.onload = function () {
	// get monitor info [(ip, port), ...]
	call_method("get_monitors", undefined, undefined, setup_monitors, "/controller/");
};
