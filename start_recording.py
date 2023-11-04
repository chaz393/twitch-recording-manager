import requests
import time


# configuration
CLIENT_ID = ""
CLIENT_SECRET = ""
STREAMER_LIST_LOCATION = ""
TEMP_DOWNLOAD_LOCATION = ""
FINISHED_DOWNLOAD_LOCATION = ""
REFRESH_INTERVAL = 60  # interval in seconds to refresh streams

# global variables
access_token = ""
access_token_expiration = 0


def start():
    while True:
        try:
            refresh_access_token_if_needed()
        except Exception as e:
            print(e)
            time.sleep(REFRESH_INTERVAL)
            continue
        try:
            streamers = get_streamers()
            print(streamers)
        except Exception as e:
            print(e)
            time.sleep(REFRESH_INTERVAL)
            continue
        try:
            update_streamer_list_file_with_names(list(streamers.keys()))
        except Exception as e:
            print(e)
            pass
        time.sleep(REFRESH_INTERVAL)


def refresh_access_token_if_needed():
    if access_token == "" or access_token_expiration < (time.time() + (REFRESH_INTERVAL * 2)):
        refresh_access_token()


def refresh_access_token():
    url = f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}" \
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
    with open(STREAMER_LIST_LOCATION, 'r') as file:
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
    headers = {'Client-Id': CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
    request = requests.get(url, headers=headers)
    response = request.json()
    streamers = {}
    for streamer in response["data"]:
        streamers[streamer["id"]] = streamer["login"]
    return streamers


def insert_streamer_id_to_name(streamer_name: str, streamer_id: str):
    old_file_contents = []
    with open(STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            old_file_contents.append(line)
    with open(STREAMER_LIST_LOCATION, 'w') as file:
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
    with open(STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            if not line.isspace() and not line.startswith("#"):
                line = line.replace("\n", "")
                streamer_name = line.split(",")[0]
                streamer_id = line.split(",")[1]
                if streamer_name in streamer_names:
                    streamers[streamer_id] = streamer_name
    return streamers


def update_streamer_list_file_with_names(streamer_ids: list):
    streamers_to_update = get_streamers_that_need_updating(streamer_ids)
    old_file_contents = []
    with open(STREAMER_LIST_LOCATION, 'r') as file:
        for line in file.readlines():
            old_file_contents.append(line)
    with open(STREAMER_LIST_LOCATION, 'w') as file:
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
    with open(STREAMER_LIST_LOCATION, 'r') as file:
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
    headers = {'Client-Id': CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
    request = requests.get(url, headers=headers)
    response = request.json()
    streamers = {}
    for streamer in response["data"]:
        streamers[streamer["id"]] = streamer["login"]
    return streamers


if __name__ == "__main__":
    start()
