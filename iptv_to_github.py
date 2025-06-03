import requests
import json
import base64
from urllib.parse import quote_plus

# IPTV Constants
PORTAL_URL = "http://portal.tiptop4k.tv/stalker_portal/server/load.php"
MAC_ADDRESS = "00:1A:79:B6:D0:06"
SN = "E7327B057414E"

# GitHub Config — UPDATE WITH YOUR NEW TOKEN
GITHUB_TOKEN = "ghp_your_new_token_here"
GITHUB_OWNER = "ALLBYNAJID"
GITHUB_REPO = "MYIPYV"
GITHUB_FILE_PATH = "playlist.m3u"  # This is the filename in your repo
GITHUB_COMMIT_MSG = "Update IPTV M3U playlist"

# Initialize session
session = requests.Session()
session.headers.update({
    'User-Agent': "StalkerTV-Free/40304.13 CFNetwork/3826.400.120 Darwin/24.3.0",
    'Cookie': f"mac={MAC_ADDRESS}; stb_lang=en_IN; timezone=Asia/Kolkata;"
})


# --- IPTV Functions ---
def get_token():
    params = {
        'type': "stb",
        'action': "handshake",
        'token': "",
        'prehash': "683A45A671F6E662B24048EB26FDA6BB377C78F1",
        'JsHttpRequest': "1-xml"
    }
    response = session.get(PORTAL_URL, params=params)
    response.raise_for_status()
    data = response.json().get("js", {})
    return data.get("token"), data.get("random")


def get_profile(token, random):
    metrics_data = {
        "mac": MAC_ADDRESS,
        "model": "MAG250",
        "type": "STB",
        "random": random,
        "sn": SN
    }
    metrics = quote_plus(json.dumps(metrics_data))
    params = {
        'type': "stb",
        'hd': "1",
        'not_valid_token': "0",
        'video_out': "hdmi",
        'action': "get_profile",
        'num_banks': "2",
        'auth_second_step': "1",
        'metrics': metrics,
        'sn': SN,
        'hw_version_2': "v2",
        'prehash': "14C9CEFDEFF4E50B70026EDB8BB61619D7EC7004",
        'JsHttpRequest': "1-xml"
    }
    headers = {'Authorization': f"Bearer {token}"}
    response = session.get(PORTAL_URL, params=params, headers=headers)
    response.raise_for_status()
    return response.json().get("js", {})


def find_channel_by_number(token, user_input_number):
    params = {
        'type': "itv",
        'action': "get_all_channels",
        'JsHttpRequest': "1-xml",
        'force_ch_link_check': ""
    }
    headers = {'Authorization': f"Bearer {token}"}
    response = session.get(PORTAL_URL, params=params, headers=headers)
    response.raise_for_status()
    js = response.json().get("js", {})
    channels = js.get("data", [])
    for channel in channels:
        if channel.get("number") == str(user_input_number):
            return {
                "number": channel.get("number"),
                "name": channel.get("name"),
                "cmd": channel.get("cmd")
            }
    return None


def get_playback_link(token, cmd):
    if not cmd:
        return None
    params = {
        'type': "itv",
        'action': "create_link",
        'cmd': cmd
    }
    headers = {'Authorization': f"Bearer {token}"}
    response = session.get(PORTAL_URL, params=params, headers=headers)
    response.raise_for_status()
    return response.json().get("js", {}).get("cmd")


def build_m3u_playlist(channels):
    lines = ["#EXTM3U"]
    for channel in channels:
        lines.append(
            f'#EXTINF:-1 tvg-id="{channel["number"]}" tvg-name="{channel["name"]}" group-title="{channel["group_title"]}",{channel["name"]}'
        )
        lines.append(channel["url"])
    return "\n".join(lines)


# --- GitHub File Update ---
def update_github_file(token, owner, repo, file_path, new_content, commit_message):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{file_path}'

    # Get existing SHA if file exists
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json()['sha']

    # Prepare and send update
    encoded_content = base64.b64encode(new_content.encode()).decode()
    payload = {
        'message': commit_message,
        'content': encoded_content
    }
    if sha:
        payload['sha'] = sha

    update_response = requests.put(url, headers=headers, json=payload)
    if update_response.status_code in [200, 201]:
        print("\n✅ GitHub file updated successfully!")
    else:
        print("❌ Failed to update GitHub file:", update_response.text)


# --- Main Flow ---
def main():
    try:
        # Set your desired channels and group names
        group_input = "2938:4K,1314:4K"

        channel_groups = {}
        for pair in group_input.split(","):
            if ":" in pair:
                num, title = pair.split(":", 1)
                channel_groups[num.strip()] = title.strip()

        token, random = get_token()
        if not (token and random):
            print("❌ Token/random not received.")
            return

        get_profile(token, random)

        channels = []
        for number in channel_groups.keys():
            print(f"\n--- Fetching Channel {number} ---")
            info = find_channel_by_number(token, number)
            if not info:
                print(f"⚠️ No channel found for {number}")
                continue

            url = get_playback_link(token, info["cmd"])
            if not url:
                print(f"⚠️ Playback link not found for {number}")
                continue

            print(f"✅ Found: {info['name']}")

            channels.append({
                "name": info["name"],
                "number": number,
                "url": url,
                "group_title": channel_groups[number]
            })

        playlist = build_m3u_playlist(channels)
        print("\nGenerated M3U Playlist:\n")
        print(playlist)

        update_github_file(
            token=GITHUB_TOKEN,
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
            file_path=GITHUB_FILE_PATH,
            new_content=playlist,
            commit_message=GITHUB_COMMIT_MSG
        )

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
