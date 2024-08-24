
def has_extension(filename: str) -> bool:
    import re
    pattern = r'\.(pdf|png|txt|jpg|jpeg)$'
    return bool(re.search(pattern, filename))

def download_from_url(url: str, save_dir: str = '.'):
    import os
    import requests
    import mimetypes

    os.makedirs(save_dir, exist_ok=True)
    filename = os.path.basename(url)
    save_path = os.path.join(save_dir, filename)
    response = requests.get(url)
    if not has_extension(filename):
        content_type = response.headers.get('Content-Type')
        extension = mimetypes.guess_extension(content_type)
        save_path += extension
    with open(save_path, 'wb') as file:
        file.write(response.content)
    return save_path

def get_repository(repo: str, token: str):
    from github import Github
    gh = Github(token)
    repo = gh.get_repo(repo)
    return repo

def to_valid_filename(text: str) -> str:
    import re
    pattern = r'\[[\d\.]+\]'
    result = re.sub(pattern, '', text)

    invalid_chars = r'[<>:"/\\|*\x00-\x1F]'
    result = re.sub(invalid_chars, '', result)
    return result.strip()

    return template

def generate_obsidian_template(additional_prop: dict | None = None):
    import datetime
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo('Asia/Tokyo'))

    creation_date_x = int(now.timestamp()*1000)
    creation_date = now.strftime("%Y-%m-%dT%H:%M:%S")

    additionals = ''
    if additional_prop is not None:
        additionals = '\n' + '\n'.join([f'{key}: {val}' for key, val in additional_prop.items()])

    template = f"""---
id: {creation_date_x}
aliases: 
tags: 
  - paper
created: {creation_date}
updated: {creation_date}{additionals}
---

"""
    return template

