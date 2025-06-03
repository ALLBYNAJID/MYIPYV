import requests
import json
import base64
from urllib.parse import quote_plus
import time

# IPTV Constants
PORTAL_URL = "https://portal.tiptop4k.tv/stalker_portal/server/load.php"  # https
MAC_ADDRESS = "00:1A:79:B6:D0:06"
SN = "E7327B057414E"

# GitHub Config — UPDATE WITH YOUR TOKEN
GITHUB_TOKEN = ""
GITHUB_OWNER = "ALLBYNAJID"
GITHUB_REPO = "MYIPYV"
GITHUB_FILE_PATH = "playlist.m3u"  # filename in your repo
GITHUB_COMMIT_MSG = "Update IPTV M3U playlist"

# Initialize session
session = requests.Session()
session.headers.update({
    'User-Agent': "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250",
    'Cookie': f"mac={MAC_ADDRESS}; stb_lang=en_IN; timezone=Asia/Kolkata;",
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'http://portal.tiptop4k.tv/stalker_portal/',
})

def get_token():
    params = {
        'type': "stb",
        'action': "handshake",
        'token': "",
        'prehash': "",
        'JsHttpRequest': "1-xml"
    }
    response = session.get(PORTAL_URL, params=params)
    print("[DEBUG][get_token] Status:", response.status_code)
    print("[DEBUG][get_token] Response:", response.text[:200])
    try:
        data = response.json().get("js", {})
        return data.get("token"), data.get("random")
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON in get_token")
        return None, None

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
        'prehash': "",
        'JsHttpRequest': "1-xml"
    }
    headers = {'Authorization': f"Bearer {token}"}
    response = session.get(PORTAL_URL, params=params, headers=headers)
    print("[DEBUG][get_profile] Status:", response.status_code)
    print("[DEBUG][get_profile] Response:", response.text[:200])
    try:
        return response.json().get("js", {})
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON in get_profile")
        return {}

def get_all_channels(token):
    params = {
        'type': "itv",
        'action': "get_all_channels",
        'JsHttpRequest': "1-xml",
        'force_ch_link_check': ""
    }
    headers = {'Authorization': f"Bearer {token}"}
    response = session.get(PORTAL_URL, params=params, headers=headers)
    print("[DEBUG][get_all_channels] Status:", response.status_code)
    print("[DEBUG][get_all_channels] Response:", response.text[:200])
    if response.status_code == 401:
        # Token expired or unauthorized
        return None
    try:
        js = response.json().get("js", {})
        return js.get("data", [])
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON in get_all_channels")
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
    print("[DEBUG][get_playback_link] Status:", response.status_code)
    print("[DEBUG][get_playback_link] Response:", response.text[:200])
    if response.status_code == 401:
        # Token expired or unauthorized
        return None, 'unauthorized'
    try:
        link = response.json().get("js", {}).get("cmd")
        return link, None
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON in get_playback_link")
        return None, 'json_error'

def build_m3u_playlist(channels):
    lines = ["#EXTM3U"]
    for channel in channels:
        lines.append(
            f'#EXTINF:-1 tvg-id="{channel["number"]}" tvg-name="{channel["name"]}" group-title="{channel["group_title"]}",{channel["name"]}'
        )
        lines.append(channel["url"])
    return "\n".join(lines)

def update_github_file(token, owner, repo, file_path, new_content, commit_message):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json'
    }
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{file_path}'

    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json()['sha']

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

def refresh_token_with_retry(retry_limit=3):
    for attempt in range(retry_limit):
        token, random = get_token()
        if token and random:
            get_profile(token, random)
            return token, random
        print(f"⚠️ Token refresh attempt {attempt+1} failed, retrying...")
        time.sleep(1)
    print("❌ Unable to get valid token after retries.")
    return None, None

def main():
    try:
        token, random = refresh_token_with_retry()
        if not (token and random):
            print("❌ Could not obtain token, exiting.")
            return

        channels_data = get_all_channels(token)
        if channels_data is None:
            # Token may have expired, try refresh once
            print("⚠️ Token expired or unauthorized. Refreshing token...")
            token, random = refresh_token_with_retry()
            if not token:
                print("❌ Failed to refresh token, exiting.")
                return
            channels_data = get_all_channels(token)
            if channels_data is None:
                print("❌ Failed to fetch channels even after token refresh.")
                return

        channels = []
        for ch in channels_data:
            number = ch.get("number")
            name = ch.get("name")
            cmd = ch.get("cmd")

            # Get playback link, retry token if unauthorized
            url, error = get_playback_link(token, cmd)
            if error == 'unauthorized':
                print(f"⚠️ Token expired while getting playback link for channel {number}. Refreshing token...")
                token, random = refresh_token_with_retry()
                if not token:
                    print("❌ Failed to refresh token during playback link retrieval, skipping channel.")
                    continue
                url, error = get_playback_link(token, cmd)

            if not url or error:
                print(f"⚠️ Could not get playback URL for channel {number} - {name}, skipping.")
                continue

            print(f"✅ Found: {name} ({number})")

            channels.append({
                "name": name,
                "number": number,
                "url": url,
                "group_title": "All Channels"
            })

        if not channels:
            print("❌ No channels found with valid playback links.")
            return

        playlist = build_m3u_playlist(channels)
        print("\nGenerated Full M3U Playlist:\n")
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
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    main()
