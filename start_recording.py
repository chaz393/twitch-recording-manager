import subprocess
import requests
import time
import psutil
import os
from RecordingThread import RecordingThread
from datetime import datetime
from config import Config


def start():
    while True:
        try:
            try:
                refresh_access_token_if_needed()
                streamers = get_streamers()
                print(f"streamers in list: {streamers}")
                try_updating_streamer_names_in_file(list(streamers.keys()))
                streams = get_streams_for_user_ids(list(streamers.keys()))
                print(f"streams live right now: {streams}")
                report_live_streamers_to_influx(streams)
                start_recording_if_not_already(streams)
            except Exception as e:
                print(e)
                time.sleep(Config.REFRESH_INTERVAL)
                continue
            time.sleep(Config.REFRESH_INTERVAL)
        except KeyboardInterrupt:
            print("stopping...")
            for thread in recording_threads.values():
                thread.stop_event.set()
            exit()



def refresh_access_token_if_needed():
    if access_token == "" or access_token_expiration < (time.time() + (Config.REFRESH_INTERVAL * 2)):
        refresh_access_token()


def refresh_access_token():
    url = f"https://id.twitch.tv/oauth2/token?client_id={Config.CLIENT_ID}&client_secret={Config.CLIENT_SECRET}" \
          f"&grant_type=client_credentials"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    request = requests.post(url, headers=headers)
    response = request.json()
    token = response["access_token"]
    expires_in = response["expires_in"]
    global access_token, access_token_expiration
    access_token = token
    access_token_expiration = time.time() + (expires_in/1000)
    print(f"refreshed token: {token}, expires at {access_token_expiration}")


def get_streamers():
    streamers = {}
    streamers_missing_id = []
    with open(Config.STREAMER_LIST_LOCATION, 'r') as file:
        lines = file.readlines()
        if len(lines) > 0:
            for line in lines:
                if not line.isspace() and not line.startswith("#"):
                    line = line.replace("\n", "")
                    streamer_name = line.split(",")[0]
                    if "," in line:
                        streamer_id = line.split(",")[1]
                    else:
                        streamer_id = ""
                    if streamer_id == "":
                        streamers_missing_id.append(streamer_name)
                    else:
                        streamers[streamer_id] = streamer_name
        if len(streamers_missing_id) > 0:
            print(f"fetching userId for the following users: {streamers_missing_id}")
            update_streamer_list_file_with_missing_ids(streamers_missing_id)
            updated_streamers = get_streamers_from_file_by_name_list(streamers_missing_id)
            for streamer_id, streamer_name in updated_streamers.items():
                streamers[streamer_id] = streamer_name
        return streamers


def update_streamer_list_file_with_missing_ids(streamers_missing_id: list):
    streamers = get_streamer_ids_by_names(streamers_missing_id)
    for streamer_id, streamer_name in streamers.items():
        insert_streamer_id_to_name(streamer_name, streamer_id)


def get_streamer_ids_by_names(usernames: list):
    first_username = True
    url = f"https://api.twitch.tv/helix/users?login="
    for username in usernames:
        if first_username:
            url = url + username
            first_username = False
        else:
            url = url + f"&login={username}"
    headers = {'Client-Id': Config.CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
    request = requests.get(url, headers=headers)
    response = request.json()
    streamers = {}
    for streamer in response["data"]:
        streamers[streamer["id"]] = streamer["login"]
    return streamers


def insert_streamer_id_to_name(streamer_name: str, streamer_id: str):
    old_file_contents = []
    with open(Config.STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            old_file_contents.append(line)
    with open(Config.STREAMER_LIST_LOCATION, 'w') as file:
        for line in old_file_contents:
            if "," in line:
                current_line_streamer_name = line.split(",")[0]
            else:
                current_line_streamer_name = line.replace("\n", "")
            if current_line_streamer_name == streamer_name:
                file.write(f"{streamer_name},{streamer_id}\n")
            else:
                file.write(f"{line}")


def get_streamers_from_file_by_name_list(streamer_names: list):
    streamers = {}
    with open(Config.STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            if not line.isspace() and not line.startswith("#"):
                line = line.replace("\n", "")
                streamer_name = line.split(",")[0]
                streamer_id = line.split(",")[1]
                if streamer_name in streamer_names:
                    streamers[streamer_id] = streamer_name
    return streamers


def try_updating_streamer_names_in_file(streamer_ids: list):
    try:
        update_streamer_list_file_with_names(streamer_ids)
    except Exception as e:
        print(e)
        pass  # updating names isn't really required, continue the flow even if this fails


def update_streamer_list_file_with_names(streamer_ids: list):
    streamers_to_update = get_streamers_that_need_updating(streamer_ids)
    if len(streamers_to_update) > 0:
        old_file_contents = []
        with open(Config.STREAMER_LIST_LOCATION, 'r') as file:
            for line in file.readlines():
                old_file_contents.append(line)
        with open(Config.STREAMER_LIST_LOCATION, 'w') as file:
            for line in old_file_contents:
                streamer_id = line.split(",")[1].replace("\n", "")
                if streamer_id in streamers_to_update:
                    old_streamer_name = line.split(",")[0]
                    print(f"updating streamer id: {streamer_id}, name: {old_streamer_name} to "
                          f"{streamers_to_update[streamer_id]}")
                    file.write(f"{streamers_to_update[streamer_id]},{streamer_id}\n")
                else:
                    file.write(line)


def get_streamers_that_need_updating(streamer_ids: list):
    updated_streamers = get_updated_streamers_by_ids(streamer_ids)
    streamers_to_update = {}
    with open(Config.STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            old_streamer_name = line.split(",")[0]
            streamer_id = line.split(",")[1].replace("\n", "")
            if updated_streamers[streamer_id] != old_streamer_name:
                streamers_to_update[streamer_id] = updated_streamers[streamer_id]
    return streamers_to_update


def get_updated_streamers_by_ids(streamer_ids: list):
    first_id = True
    url = f"https://api.twitch.tv/helix/users?id="
    for streamer_id in streamer_ids:
        if first_id:
            url = url + streamer_id
            first_id = False
        else:
            url = url + f"&id={streamer_id}"
    headers = {'Client-Id': Config.CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
    request = requests.get(url, headers=headers)
    response = request.json()
    streamers = {}
    for streamer in response["data"]:
        streamers[streamer["id"]] = streamer["login"]
    return streamers


def get_streams_for_user_ids(stream_ids: list):
    url = "https://api.twitch.tv/helix/streams?user_id="
    first_user = True
    for stream_id in stream_ids:
        if first_user:
            url = url + stream_id
            first_user = False
        else:
            url = url + f"&user_id={stream_id}"
    headers = {'Client-Id': Config.CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
    request = requests.get(url, headers=headers)
    response = request.json()
    streams_response = response["data"]
    streams = {}
    if len(streams_response) > 0:
        for stream in streams_response:
            streamer_name = stream["user_login"]
            stream_title = stream["title"]
            streams[streamer_name] = strip_illegal_chars_from_title(stream_title)
    return streams


def strip_illegal_chars_from_title(title: str):
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789_-"
    title = title.replace(" ", "_")
    for char in title:
        if char not in allowed_chars:
            title = title.replace(char, "")
    return title


def report_live_streamers_to_influx(streams: dict):
    if Config.INFLUX_REPORTING_URL != "":
        for streamer_name, stream_title in streams.items():
            url = Config.INFLUX_REPORTING_URL
            body = Config.INFLUX_LIVE_STREAMERS_REPORTING_PAYLOAD\
                .format(streamer_name=streamer_name, stream_title=stream_title)
            try:
                requests.post(url, data=body)
            except Exception as e:
                print(e)
                pass  # if this fails it's not a big deal


def start_recording_if_not_already(streams: dict):
    for streamer_name, stream_title in streams.items():
        process_exists = does_process_exist_for_streamer(streamer_name)
        if not process_exists:
            print(f"{streamer_name} process does not exist, starting now")
            streamer_directory = f"{Config.DOWNLOAD_LOCATION}/{streamer_name}/"
            current_time = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            filename = f"{streamer_name}_TwitchVOD_{current_time}_{stream_title}.mp4"
            full_path = streamer_directory + filename
            create_streamer_folder_if_not_exists(streamer_directory)
            start_recording(filename, full_path, streamer_name)


def does_process_exist_for_streamer(streamer_name: str):
    streamlink_found = False
    streamer_name_found = False
    mp4_found = False
    for proc in psutil.process_iter():
        try:
            for arg in proc.cmdline():
                if "streamlink" in arg:
                    streamlink_found = True
                if streamer_name in arg:
                    streamer_name_found = True
                if "mp4" in arg:
                    mp4_found = True
                if streamlink_found and streamer_name_found and mp4_found:
                    return True
        except psutil.ZombieProcess:
            continue
    return False


def create_streamer_folder_if_not_exists(streamer_directory: str):
    if not os.path.exists(streamer_directory):
        os.mkdir(streamer_directory)


def start_recording(filename: str, full_path: str, streamer_name: str):
    thread = RecordingThread(streamer_name, filename, full_path, recording_thread_finished_callback)
    thread.start()
    recording_threads[thread.ident] = thread


def recording_thread_finished_callback(threadd_ident: int, streamer_name: str, filename: str, full_path: str):
    recording_threads.pop(threadd_ident)
    if Config.RECORDING_FINISHED_HOOK_SCRIPT != "":
        subprocess.Popen(["bash", Config.RECORDING_FINISHED_HOOK_SCRIPT, streamer_name, filename, full_path])


# global variables
recording_threads = {}
access_token = ""
access_token_expiration = 0

if __name__ == "__main__":
    start()
