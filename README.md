# twitch-recording-manager
This project will automate the recording of twitch streams. The recording is done using Streamlink


The streamer file will store both the username and respective unique user ID in essentially csv format
A user can change their username at any given time so you can't consistently lookup a user based on username, you need something that won't ever change. The user ID will never change for a given user
So you can start off by putting a username in the file and this script will fetch the user ID associated with that username and put it on the same line separated by a comma
All future lookups for that user will by user ID not username. The username is only kept in the file for readability
This script will even update the username in the file if the user changes their username. Again this is irrelevant to the script but helps with human readability

You can configure a bash hook script to run when a recording completes, this will get called with the arguments streamer_name and full_path which is the full path to the recorded video file
This can be helpful when you want to run post processing on the completed recording or move it to colder storage

You can also configure reporting currently live streamers to influxdb for monitoring in grafana. You can set the infux url for the http api and the payload. streamer_name and stream_title will be inserted into the payload string, so you can use "{streamer_name}" and "{stream_title}" in the string and they will be replaced with the streamer name and title respectively when the request body is built
