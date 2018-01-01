/**
 *  Copyright 2017 Ryan Finnie
 *
 *  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 *  in compliance with the License. You may obtain a copy of the License at:
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 *  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License
 *  for the specific language governing permissions and limitations under the License.
 *
 */

import groovy.json.JsonOutput

metadata {
	definition (name: "ESP8266 RGB", namespace: "rfinnie", author: "Ryan Finnie") {
		capability "Switch Level"
		capability "Actuator"
		capability "Color Control"
		capability "Switch"
		capability "Refresh"

		command "demo"
		command "refresh"
		command "resetcolor"
		command "resetdevice"
	}

	preferences {
		section() {
			input name: "pwmFrequency", type: "number", title: "PWM frequency [Hz]", defaultValue: 100, range: "1..1000"
			input name: "fadeTime", type: "number", title: "Transition fade time [ms]", defaultValue: 1000, range: "0..10000"
			input name: "deviceAuth", type: "password", title: "Device authentication (optional)"
		}
	}

tiles(scale: 2) {
		multiAttributeTile(name:"switch", type: "lighting", width: 6, height: 4, canChangeIcon: true) {
			tileAttribute ("device.switch", key: "PRIMARY_CONTROL") {
				attributeState "on", label:'${name}', action:"switch.off", icon:"st.lights.philips.hue-single", backgroundColor:"#00A0DC", nextState:"turningOff"
				attributeState "off", label:'${name}', action:"switch.on", icon:"st.lights.philips.hue-single", backgroundColor:"#ffffff", nextState:"turningOn"
				attributeState "turningOn", label:'${name}', action:"switch.off", icon:"st.lights.philips.hue-single", backgroundColor:"#00A0DC", nextState:"turningOff"
				attributeState "turningOff", label:'${name}', action:"switch.on", icon:"st.lights.philips.hue-single", backgroundColor:"#ffffff", nextState:"turningOn"
			}
			tileAttribute ("device.level", key: "SLIDER_CONTROL") {
				attributeState "level", action:"switch level.setLevel"
			}
			tileAttribute ("device.color", key: "COLOR_CONTROL") {
				attributeState "color", action:"setColor"
			}
		}

		valueTile("color", "device.color", inactiveLabel: false, decoration: "flat", width: 2, height: 2) {
			state "color", label: '${currentValue}'
		}

		standardTile("resetcolor", "device.resetcolor", inactiveLabel: false, decoration: "flat", width: 2, height: 2) {
			state "resetcolor", label:"Reset Color", action:"resetcolor", icon:"st.lights.philips.hue-single", defaultState: true
		}
		standardTile("refresh", "device.switch", inactiveLabel: false, decoration: "flat", width: 2, height: 2) {
			state "refresh", label:"", action:"refresh.refresh", icon:"st.secondary.refresh", defaultState: true
		}
		standardTile("resetdevice", "device.resetdevice", inactiveLabel: false, decoration: "flat", width: 2, height: 2) {
			state "resetdevice", label:"Reset Device", action:"resetdevice", icon:"st.lights.philips.hue-single", defaultState: true
		}
		standardTile("demo", "device.demo", inactiveLabel: false, decoration: "flat", width: 2, height: 2) {
			state "demo", label:"Demo", action:"demo", icon:"st.lights.philips.hue-single", defaultState: true
		}

		main(["switch"])
		details(["switch", "color", "refresh", "resetcolor", "resetdevice", "demo"])
	}
}

def parse(description) {
	log.debug "parse: $description"
	def msg = parseLanMessage(description)
	def status = msg.status
	def json = msg.json
	log.debug msg.json

	if (json.state) {
		if (json.state.red) { sendEvent(name: "red", value: json.state.red)}
		if (json.state.green) { sendEvent(name: "green", value: json.state.green)}
		if (json.state.blue) { sendEvent(name: "blue", value: json.state.blue)}
		if (json.state.hue) { sendEvent(name: "hue", value: json.state.hue)}
		if (json.state.saturation) { sendEvent(name: "saturation", value: json.state.saturation)}
		if (json.state.level) { sendEvent(name: "level", value: json.state.level)}
		if (json.state.switch) { sendEvent(name: "switch", value: json.state.switch)}
	}
}

private Integer convertHexToInt(hex) {
	Integer.parseInt(hex,16)
}

private String convertHexToIP(hex) {
	//log.debug("Convert hex to ip: $hex") 
	[convertHexToInt(hex[0..1]),convertHexToInt(hex[2..3]),convertHexToInt(hex[4..5]),convertHexToInt(hex[6..7])].join(".")
}

private String convertIPtoHex(ipAddress) { 
	String hex = ipAddress.tokenize( '.' ).collect { String.format( '%02x', it.toInteger() ) }.join()
	//log.debug "IP address entered is $ipAddress and the converted hex code is $hex"
	return hex

}

private String convertPortToHex(port) {
	String hexport = port.toString().format( '%04x', port.toInteger() )
	//log.debug hexport
	return hexport
}

private getHostAddress() {
	def parts = device.deviceNetworkId.split(":")
	def ip = convertHexToIP(parts[0])
	def port = convertHexToInt(parts[1])
	return ip + ":" + port
}

private sendHTTPRequest(data) {
	def json = JsonOutput.toJson(data)
	def result = new physicalgraph.device.HubAction(
		method: "POST",
		path: "/command",
		body: json,
		headers: [
			HOST: getHostAddress(),
			"Content-Type": "application/json",
		]
	)
	result
}

def on() {
	log.debug "Turning light on"
	sendHTTPRequest([
		auth: settings.deviceAuth,
		state: [
			switch: "on",
			frequency: settings.pwmFrequency,
			fadetime: settings.fadeTime
		]
	])
}

def off() {
	log.debug "Turning light off"
	sendHTTPRequest([
		auth: settings.deviceAuth,
		state: [
			switch: "off",
			frequency: settings.pwmFrequency,
			fadetime: settings.fadeTime
		]
	])
}

def setLevel(percent) {
	log.debug "setLevel: ${percent}"
	sendEvent(name: "level", value: percent)

	sendHTTPRequest([
		auth: settings.deviceAuth,
		state: [
			level: percent,
			frequency: settings.pwmFrequency,
			fadetime: settings.fadeTime
		]
	])
}

def setColor(value) {
	log.debug "setColor: ${value}"
	sendHTTPRequest([
		auth: settings.deviceAuth,
		state: [
			level: value.level,
			switch: value.switch,
			red: value.red,
			green: value.green,
			blue: value.blue,
			hue: value.hue,
			saturation: value.saturation,
			frequency: settings.pwmFrequency,
			fadetime: settings.fadeTime
		]
	])
}

def resetcolor() {
	log.debug "Reset Color"
	setColor([
		level:100,
		red:253,
		green:248,
		blue:236
	])
}

def resetdevice() {
	log.debug "Reset Device"
	sendHTTPRequest([
		auth: settings.deviceAuth,
		cmd: "reset"
	])
}

def demo() {
	log.debug "Demo"
	sendHTTPRequest([
		auth: settings.deviceAuth,
		cmd: "demo"
	])
}

def refresh() {
	log.debug "Refresh"
	sendHTTPRequest([
		auth: settings.deviceAuth,
	])
}
